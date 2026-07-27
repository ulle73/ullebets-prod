import { createCache } from "./cache.js";
import { logServerBacktestStep } from "./logger.js";
import { STAT_PATTERNS, PERIODS, DEFAULT_FORM } from "./constants.js";
import { clamp, poissonCdf } from "./math.js";
import { buildTuples, teamSlug } from "./tuples.js";
import { computeBaseProjection } from "./methods/base.js";
import { computeMultiplierProjection } from "./methods/multiplier.js";
import { computeLeagueAverageProjection } from "./methods/leagueAverage.js";
import { computeMultifactorProjection } from "./methods/multifactor.js";
import { getFormulaConfig } from "./formulaConfig.js";
import { runFormulas } from "./formulas/index.js";

const RESULT_CACHE = createCache({ ttlMs: 45 * 60 * 1000 });

// --- Start of utility functions (no changes) ---
function readPeriodValue(stat, periodKey) {
  if (!stat) return null;
  const entry = stat?.[periodKey] ?? (periodKey !== "ALL" ? stat?.ALL : null);
  if (!entry) return null;
  const raw = typeof entry === "object" ? entry.value ?? entry.avg ?? entry.mean : entry;
  const numeric = Number(raw);
  return Number.isFinite(numeric) ? numeric : null;
}

function readProfileStatValue(profile, sectionKey, statKey, periodKey) {
  if (!profile) return null;
  const section = profile?.statistics?.[sectionKey];
  if (!section?.[statKey]) return null;
  return readPeriodValue(section[statKey], periodKey);
}

function readProfileLeagueAverageValue(profile, sectionKey, statKey, periodKey) {
  if (!profile) return null;
  const section = profile?.statistics?.leagueAverage?.[sectionKey];
  if (!section?.[statKey]) return null;
  return readPeriodValue(section[statKey], periodKey);
}

function aggregateBundleMetric(bundle, matchTypes, reader) {
  const values = [];
  for (const matchType of matchTypes) {
    const profile = bundle?.[matchType];
    if (!profile) continue;
    const value = reader(profile);
    if (Number.isFinite(value)) {
      values.push(value);
    }
  }
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function computeLambdaFromMetrics(attack, attackAvg, concede, concedeAvg, overallAverage) {
  if (
    Number.isFinite(attack) &&
    Number.isFinite(attackAvg) &&
    attackAvg > 0 &&
    Number.isFinite(concede) &&
    Number.isFinite(concedeAvg) &&
    concedeAvg > 0 &&
    Number.isFinite(overallAverage)
  ) {
    return (attack / attackAvg) * (concede / concedeAvg) * overallAverage;
  }

  const fallbackCandidates = [attack, concede].filter((value) => Number.isFinite(value));
  if (fallbackCandidates.length) {
    return fallbackCandidates.reduce((sum, value) => sum + value, 0) / fallbackCandidates.length;
  }

  if (Number.isFinite(overallAverage)) {
    return overallAverage;
  }

  return null;
}

function buildTeamProfileProjection({
  homeBundle,
  awayBundle,
  statKey,
  periodKey,
  neutralGround,
}) {
  const homeMatchTypes = neutralGround ? ["home", "away"] : ["home"];
  const awayMatchTypes = neutralGround ? ["home", "away"] : ["away"];

  const homeAttack = aggregateBundleMetric(homeBundle, homeMatchTypes, (profile) =>
    readProfileStatValue(profile, "for", statKey, periodKey)
  );
  const homeConcede = aggregateBundleMetric(homeBundle, homeMatchTypes, (profile) =>
    readProfileStatValue(profile, "against", statKey, periodKey)
  );
  const awayAttack = aggregateBundleMetric(awayBundle, awayMatchTypes, (profile) =>
    readProfileStatValue(profile, "for", statKey, periodKey)
  );
  const awayConcede = aggregateBundleMetric(awayBundle, awayMatchTypes, (profile) =>
    readProfileStatValue(profile, "against", statKey, periodKey)
  );

  const homeAttackAvg = aggregateBundleMetric(homeBundle, homeMatchTypes, (profile) =>
    readProfileLeagueAverageValue(profile, "for", statKey, periodKey)
  );
  const homeConcedeAvg = aggregateBundleMetric(homeBundle, homeMatchTypes, (profile) =>
    readProfileLeagueAverageValue(profile, "against", statKey, periodKey)
  );
  const awayAttackAvg = aggregateBundleMetric(awayBundle, awayMatchTypes, (profile) =>
    readProfileLeagueAverageValue(profile, "for", statKey, periodKey)
  );
  const awayConcedeAvg = aggregateBundleMetric(awayBundle, awayMatchTypes, (profile) =>
    readProfileLeagueAverageValue(profile, "against", statKey, periodKey)
  );

  const overallCandidates = [
    homeAttackAvg,
    homeConcedeAvg,
    awayAttackAvg,
    awayConcedeAvg,
  ].filter((value) => Number.isFinite(value));

  let overallAverage = overallCandidates.length
    ? overallCandidates.reduce((sum, value) => sum + value, 0) / overallCandidates.length
    : null;

  if (!Number.isFinite(overallAverage)) {
    const fallback = [homeAttack, homeConcede, awayAttack, awayConcede].filter((value) =>
      Number.isFinite(value)
    );
    overallAverage = fallback.length
      ? fallback.reduce((sum, value) => sum + value, 0) / fallback.length
      : null;
  }

  const lambdaHome = computeLambdaFromMetrics(
    homeAttack,
    homeAttackAvg,
    awayConcede,
    awayConcedeAvg,
    overallAverage
  );
  const lambdaAway = computeLambdaFromMetrics(
    awayAttack,
    awayAttackAvg,
    homeConcede,
    homeConcedeAvg,
    overallAverage
  );

  return {
    lambdaHome,
    lambdaAway,
    metrics: {
      homeAttack,
      homeConcede,
      awayAttack,
      awayConcede,
      homeAttackAvg,
      homeConcedeAvg,
      awayAttackAvg,
      awayConcedeAvg,
      overallAverage,
    },
  };
}

function buildCacheKey(params) {
  return JSON.stringify(params, Object.keys(params).sort());
}

function parseFormValue(form) {
  if (form === undefined || form === null) return DEFAULT_FORM;
  if (String(form).toLowerCase() === "all") return Infinity;
  const parsed = Number.parseInt(form, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : Infinity;
}

function validateScope(scope) {
  const normalized = String(scope || "total").toLowerCase();
  if (["home", "away", "total"].includes(normalized)) {
    return normalized;
  }
  return "total";
}

function validatePeriod(period) {
  const normalized = String(period || "ALL").toUpperCase();
  if (PERIODS.includes(normalized)) {
    return normalized;
  }
  return "ALL";
}

function validateImportance(value, fallback = 5) {
  const numeric = Number.parseInt(value, 10);
  if (!Number.isFinite(numeric)) return fallback;
  return clamp(1, numeric, 10);
}

function parseOdds(value) {
  if (value === undefined || value === null || value === "") return null;
  const numeric = Number.parseFloat(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

function computePoissonProbability(lambda, line, isOver) {
  if (!Number.isFinite(lambda)) return null;
  const safeLambda = lambda > 0 ? lambda : 0.0001;
  const k = isOver ? Math.max(-1, Math.ceil(line) - 1) : Math.floor(line);
  const cdfVal = poissonCdf(k, safeLambda);
  return Math.min(1, Math.max(0, isOver ? 1 - cdfVal : cdfVal));
}

function mapMatchesForOutput(tuples, statKey, slug, role, neutralGround) {
  return tuples
    .filter((tuple) => {
      const homeSlug = teamSlug(tuple.meta.homeTeamName || tuple.meta.homeTeam || tuple.meta.home);
      const awaySlug = teamSlug(tuple.meta.awayTeamName || tuple.meta.awayTeam || tuple.meta.away);
      const isHome = homeSlug === slug;
      const isAway = awaySlug === slug;
      if (role === "home") {
        return neutralGround ? isAway : isHome;
      }
      return isAway;
    })
    .map((tuple) => ({
      homeTeam: tuple.meta.homeTeamName || tuple.meta.homeTeam || tuple.meta.home,
      awayTeam: tuple.meta.awayTeamName || tuple.meta.awayTeam || tuple.meta.away,
      stat: tuple.data[statKey],
      totalShots: tuple.data.totalShots,
      timestamp: tuple.meta.timestamp,
      matchId: tuple.meta.matchId || tuple.meta.id,
    }));
}

function collectConceded(tuples, statKey, slug, role, neutralGround) {
  return tuples
    .filter((tuple) => {
      const homeSlug = teamSlug(tuple.meta.homeTeamName || tuple.meta.homeTeam || tuple.meta.home);
      const awaySlug = teamSlug(tuple.meta.awayTeamName || tuple.meta.awayTeam || tuple.meta.away);
      
      if (role === "home") {
        return neutralGround
          ? awaySlug === slug
          : homeSlug === slug;
      }
      return awaySlug === slug;
    })
    .map((tuple) => {
      if (role === "home") {
        return neutralGround ? tuple.data[statKey]?.home : tuple.data[statKey]?.away;
      }
      return tuple.data[statKey]?.home;
    })
    .filter((value) => Number.isFinite(value));
}


function findTeamOpta(leaguesData, teamName) {
  if (!leaguesData || !teamName) return null;
  const normalized = String(teamName).toLowerCase().trim();
  
  for (const league of Object.values(leaguesData)) {
    if (!league.teams) continue;
    for (const team of league.teams) {
      if (String(team.name).toLowerCase().trim() === normalized) {
        return {
          rank: team.optaRank,
          rating: team.optaRating,
        };
      }
    }
  }
  return null;
}


/**
 * Performs the core EV calculation, assuming all data has been pre-fetched.
 */
export async function calculateEVFromData(params, fetchedData) {
    const {
        homeTeam,
        awayTeam,
        over = true,
        line,
        scope = "total",
        stat = "totalShots",
        period = "ALL",
        form = DEFAULT_FORM,
        odds,
        neutralGround = false,
        home_importance = 5,
        away_importance = 5,
      } = params;
    
      const { homeBundle, awayBundle, homeMatchesRaw, awayMatchesRaw, leaguesData, leagueRankings } = fetchedData;

      // --- Start of calculation logic (copied from original computeExpectedValue) ---
      const parsedLine = Number.parseFloat(line);
      const parsedScope = validateScope(scope);
      const parsedPeriod = validatePeriod(period);
      const parsedForm = parseFormValue(form);
      const parsedOdds = parseOdds(odds);
      const homeImportance = validateImportance(home_importance);
      const awayImportance = validateImportance(away_importance);
      const formulaConfig = getFormulaConfig(stat);
      const statProfileKey = STAT_PATTERNS[stat]?.rankKey || stat;

      if (!homeBundle || (!homeBundle.home && !homeBundle.away)) {
        throw new Error(`Kunde inte hitta teamprofile för ${homeTeam}.`);
      }
    
      if (!awayBundle || (!awayBundle.home && !awayBundle.away)) {
        throw new Error(`Kunde inte hitta teamprofile för ${awayTeam}.`);
      }

      const projection = buildTeamProfileProjection({
        homeBundle,
        awayBundle,
        statKey: statProfileKey,
        periodKey: parsedPeriod,
        neutralGround,
      });
    
      const homeSlug = teamSlug(homeTeam);
      const awaySlug = teamSlug(awayTeam);
    
      const tuples = buildTuples({
        homeMatches: homeMatchesRaw,
        awayMatches: awayMatchesRaw,
        statKey: stat,
        periodKey: parsedPeriod,
      });
    
      if (!tuples.length) {
        throw new Error("Kunde inte hitta några matcher för valda lag.");
      }
    
      const OVER = Boolean(over);
      const LINE = parsedLine;
      const oddsValue = parsedOdds;
      const implied = oddsValue ? 1 / oddsValue : 0;
    
      const baseResult = computeBaseProjection({
        tuples,
        statKey: stat,
        scope: parsedScope,
        over: OVER,
        line: LINE,
        formLimit: parsedForm,
        homeSlug,
        awaySlug,
        homeImportance,
        awayImportance,
        neutralGround,
        blendWeight: formulaConfig.blendWeight,
      });
    
      const multiplierResult = computeMultiplierProjection({
        base: baseResult,
        tuples,
        homeSlug,
        awaySlug,
      });
    
      const leagueProjection = await computeLeagueAverageProjection({
        homeTeam,
        awayTeam,
        statKey: statProfileKey,
        periodKey: parsedPeriod,
        scope: parsedScope,
        neutralGround,
        leagueRankings,
        leaguesData,
      });
    
      const multifactorProjection = computeMultifactorProjection({
        base: baseResult,
        leagueProjection,
        weights: formulaConfig.multifactor,
      });
    
      const totalMatches = baseResult.statsFor.length || baseResult.teamTuples?.length || tuples.length;
      
      const meanFor = Number.isFinite(baseResult.meanFor)
        ? Number(baseResult.meanFor.toFixed(2))
        : 0;
      const meanAgainst = Number.isFinite(baseResult.meanAgainst)
        ? Number(baseResult.meanAgainst.toFixed(2))
        : 0;
      const baseLambda = Number.isFinite(baseResult.lambda)
        ? Number(baseResult.lambda.toFixed(2))
        : null;
    
      const probabilityOf = (lambda) => computePoissonProbability(lambda, LINE, OVER);

      const homeOpta = findTeamOpta(leaguesData, homeTeam);
      const awayOpta = findTeamOpta(leaguesData, awayTeam);

      const formulaResults = runFormulas({
        baseResult,
        multiplierResult,
        leagueProjection,
        multifactorProjection,
        oddsValue,
        implied,
        probabilityOf,
        homeOpta,
        awayOpta,
        homeBundle,
        awayBundle,
        homeMatchesRaw,
        awayMatchesRaw,
        params: {
          statKey: stat,
          scope: parsedScope,
          period: parsedPeriod,
          line: LINE,
          over: OVER,
          matchDate: params.matchDate ?? params.date ?? null,
          underOdds: params.underOdds ?? null,
        },
      });

      // ... (previous code)

      const homeMatchTypes = neutralGround ? ["home", "away"] : ["home"];
      const awayMatchTypes = neutralGround ? ["home", "away"] : ["away"];

      const homeHistory = getMergedHistory(homeBundle, statProfileKey, parsedPeriod, homeMatchTypes);
      const awayHistory = getMergedHistory(awayBundle, statProfileKey, parsedPeriod, awayMatchTypes);

      const result = {
        params: {
          home: homeTeam,
          away: awayTeam,
          over: OVER,
          line: LINE,
          scope: parsedScope,
          stat,
          period: parsedPeriod,
          form,
          neutralGround,
          odds: oddsValue,
          homeImportance,
          awayImportance,
        },
        ...formulaResults,
        timestamp: new Date().toISOString(),
        matches: totalMatches,
        statsFor: baseResult.statsFor,
        statsAgainst: baseResult.statsAgainst,
        hitsOver: `${baseResult.hits.over}/${totalMatches}`,
        hitsUnder: `${baseResult.hits.under}/${totalMatches}`,
        hitsExact: `${baseResult.hits.exact}/${totalMatches}`,
        meanFor,
        meanAgainst,
        lambda: baseLambda,
        homeConceded: collectConceded(tuples, stat, homeSlug, "home", neutralGround),
        awayConceded: collectConceded(tuples, stat, awaySlug, "away", neutralGround),
        hitsAgainst: `${baseResult.hits.against}/${totalMatches}`,
        homeMatches: mapMatchesForOutput(tuples, stat, homeSlug, "home", neutralGround),
        awayMatches: mapMatchesForOutput(tuples, stat, awaySlug, "away", neutralGround),
        leagueAvgHistory: projection.metrics,
        homeHistory,
        awayHistory,
      };
      // --- End of calculation logic ---

      return result;
}

function getMergedHistory(bundle, statKey, periodKey, matchTypes = ["home", "away"]) {
  const history = [];
  
  const extract = (profile, type) => {
    if (!profile?.statistics?.for?.[statKey]?.[periodKey]?.history) return;
    const raw = profile.statistics.for[statKey][periodKey].history;
    console.log(`[getMergedHistory] Extracting ${raw.length} items for ${statKey} ${periodKey} (${type})`);
    if (Array.isArray(raw)) {
        history.push(...raw);
    }
  };
  
  console.log("[getMergedHistory] Bundle keys:", Object.keys(bundle || {}));
  
  for (const type of matchTypes) {
      if (bundle?.[type]) {
          extract(bundle[type], type);
      }
  }
  
  // Deduplicate by matchId
  const seen = new Set();
  const unique = [];
  for (const item of history) {
    if (item.matchId && !seen.has(item.matchId)) {
      seen.add(item.matchId);
      unique.push(item);
    }
  }
  
  // Sort by date desc
  return unique.sort((a, b) => new Date(b.date) - new Date(a.date));
}


export async function computeExpectedValue(params) {
  throw new Error("computeExpectedValue is disabled in the V2 model runtime. Use calculateEVFromData with injected fetchedData.");
}
