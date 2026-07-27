import { PERIODS } from "../constants.js";
import { normalizeTeamName } from "../tuples.js";

function findLeagueBlock(rankings, leagueName) {
  if (!Array.isArray(rankings)) return null;
  return rankings.find((entry) => entry?.league?.name === leagueName || entry?.league === leagueName);
}

function findLeagueByTeam(rankings, teamName) {
  const normalized = normalizeTeamName(teamName);
  for (const entry of rankings || []) {
    const teams = entry?.ranking;
    if (!teams || typeof teams !== "object") continue;
    for (const statKey of Object.values(teams)) {
      const forSection = statKey?.for;
      if (!forSection) continue;
      for (const period of Object.values(forSection)) {
        if (!Array.isArray(period)) continue;
        if (period.some((team) => normalizeTeamName(team.team) === normalized)) {
          return entry?.league?.name || entry?.league;
        }
      }
    }
  }
  return null;
}

function computeOverallAverage(stat, periodKey) {
  const avg = stat?.leagueAverage;
  if (!avg) return null;
  if (Number.isFinite(avg?.[periodKey])) return avg[periodKey];
  if (periodKey !== "ALL" && Number.isFinite(avg?.ALL)) return avg.ALL;
  const values = Object.values(avg).filter((val) => Number.isFinite(val));
  if (!values.length) return null;
  return values.reduce((sum, val) => sum + val, 0) / values.length;
}

function getPeriodEntries(section, periodKey) {
  if (!section) return null;
  if (Array.isArray(section[periodKey]) && section[periodKey].length) {
    return section[periodKey];
  }
  if (periodKey !== "ALL" && Array.isArray(section.ALL) && section.ALL.length) {
    return section.ALL;
  }
  const firstArray = Object.values(section).find(
    (value) => Array.isArray(value) && value.length
  );
  return firstArray || null;
}

function findTeamEntry(entries, teamName) {
  if (!Array.isArray(entries)) return null;
  const normalized = normalizeTeamName(teamName);
  return (
    entries.find((entry) => normalizeTeamName(entry.team) === normalized) ||
    entries.find((entry) => normalizeTeamName(entry.team).includes(normalized)) ||
    null
  );
}

function valueFromEntry(entry, location) {
  if (!entry) return null;
  const home = Number(entry.home_rawValue ?? entry.homeValue);
  const away = Number(entry.away_rawValue ?? entry.awayValue);
  const hasHome = Number.isFinite(home);
  const hasAway = Number.isFinite(away);
  if (!hasHome && !hasAway) return null;
  if (location === "both") {
    const values = [];
    if (hasHome) values.push(home);
    if (hasAway) values.push(away);
    return values.length ? values.reduce((sum, val) => sum + val, 0) / values.length : null;
  }
  if (location === "home") {
    return hasHome ? home : hasAway ? away : null;
  }
  if (location === "away") {
    return hasAway ? away : hasHome ? home : null;
  }
  return null;
}

function averageEntries(entries, location) {
  if (!Array.isArray(entries) || !entries.length) return null;
  const values = entries
    .map((entry) => valueFromEntry(entry, location))
    .filter((val) => Number.isFinite(val));
  if (!values.length) return null;
  return values.reduce((sum, val) => sum + val, 0) / values.length;
}

function computeSinglePeriodProjection({
  periodKey,
  homeTeam,
  awayTeam,
  homeStat,
  awayStat,
  neutralGround,
}) {
  const attackLocationHome = neutralGround ? "both" : "home";
  const defendLocationAway = neutralGround ? "both" : "away";
  const attackLocationAway = neutralGround ? "both" : "away";
  const defendLocationHome = neutralGround ? "both" : "home";

  const homeAttackEntries = getPeriodEntries(homeStat?.for, periodKey);
  const homeAttack = valueFromEntry(
    findTeamEntry(homeAttackEntries, homeTeam),
    attackLocationHome
  );
  const homeAttackAvg = averageEntries(homeAttackEntries, attackLocationHome);

  const awayConcedeEntries = getPeriodEntries(awayStat?.against, periodKey);
  const awayConcede = valueFromEntry(
    findTeamEntry(awayConcedeEntries, awayTeam),
    defendLocationAway
  );
  const awayConcedeAvg = averageEntries(awayConcedeEntries, defendLocationAway);

  const awayAttackEntries = getPeriodEntries(awayStat?.for, periodKey);
  const awayAttack = valueFromEntry(
    findTeamEntry(awayAttackEntries, awayTeam),
    attackLocationAway
  );
  const awayAttackAvg = averageEntries(awayAttackEntries, attackLocationAway);

  const homeConcedeEntries = getPeriodEntries(homeStat?.against, periodKey);
  const homeConcede = valueFromEntry(
    findTeamEntry(homeConcedeEntries, homeTeam),
    defendLocationHome
  );
  const homeConcedeAvg = averageEntries(homeConcedeEntries, defendLocationHome);

  const overallCandidates = [
    computeOverallAverage(homeStat, periodKey),
    computeOverallAverage(awayStat, periodKey),
  ].filter((val) => Number.isFinite(val));

  let overallAverage = overallCandidates.length
    ? overallCandidates.reduce((sum, val) => sum + val, 0) / overallCandidates.length
    : null;

  if (!Number.isFinite(overallAverage)) {
    const fallback = [homeAttackAvg, awayAttackAvg, homeConcedeAvg, awayConcedeAvg].filter((val) =>
      Number.isFinite(val)
    );
    overallAverage =
      fallback.length > 0
        ? fallback.reduce((sum, val) => sum + val, 0) / fallback.length
        : null;
  }

  if (
    [homeAttack, homeAttackAvg, awayConcede, awayConcedeAvg, overallAverage].some(
      (val) => !Number.isFinite(val)
    )
  ) {
    return null;
  }

  const lambdaHome = (homeAttack / homeAttackAvg) * (awayConcede / awayConcedeAvg) * overallAverage;
  const lambdaAway = (awayAttack / awayAttackAvg) * (homeConcede / homeConcedeAvg) * overallAverage;
  const lambdaTotal = lambdaHome + lambdaAway;

  const format = (value) => (Number.isFinite(value) ? value.toFixed(2) : "n/a");

  return {
    period: periodKey,
    home: {
      lambda: lambdaHome,
      formula: `(${format(homeAttack)} / ${format(homeAttackAvg)}) * (${format(
        awayConcede
      )} / ${format(awayConcedeAvg)}) * ${format(overallAverage)} = ${format(lambdaHome)}`,
    },
    away: {
      lambda: lambdaAway,
      formula: `(${format(awayAttack)} / ${format(awayAttackAvg)}) * (${format(
        homeConcede
      )} / ${format(homeConcedeAvg)}) * ${format(overallAverage)} = ${format(lambdaAway)}`,
    },
    total: {
      lambda: lambdaTotal,
      formula: `${format(lambdaHome)} + ${format(lambdaAway)} = ${format(lambdaTotal)}`,
    },
  };
}

export async function computeLeagueAverageProjection({
  homeTeam,
  awayTeam,
  statKey,
  periodKey,
  scope,
  neutralGround,
  leagueRankings = [],
  leaguesData = {},
}) {
  const normalizedHome = normalizeTeamName(homeTeam);
  const normalizedAway = normalizeTeamName(awayTeam);

  const teamToLeague = new Map();
  for (const [leagueName, info] of Object.entries(leaguesData || {})) {
    for (const team of info?.teams || []) {
      teamToLeague.set(normalizeTeamName(team.name), leagueName);
    }
  }

  const homeLeagueName = teamToLeague.get(normalizedHome) || findLeagueByTeam(leagueRankings, homeTeam);
  const awayLeagueName = teamToLeague.get(normalizedAway) || findLeagueByTeam(leagueRankings, awayTeam);

  if (!homeLeagueName || !awayLeagueName) {
    return { lambda: null, selectedLambda: null, scope, reason: "missing-league" };
  }

  const homeLeagueBlock = findLeagueBlock(leagueRankings, homeLeagueName);
  const awayLeagueBlock = findLeagueBlock(leagueRankings, awayLeagueName);

  if (!homeLeagueBlock || !awayLeagueBlock) {
    return {
      lambda: null,
      selectedLambda: null,
      scope,
      reason: "missing-league-block",
    };
  }

  const homeStat = homeLeagueBlock?.ranking?.[statKey];
  const awayStat = awayLeagueBlock?.ranking?.[statKey];

  if (!homeStat || !awayStat) {
    return { lambda: null, selectedLambda: null, scope, reason: "missing-stat" };
  }

  const lambdaPeriods = periodKey ? [periodKey] : ["ALL"];
  const reportPeriods = Array.from(new Set([...PERIODS, ...lambdaPeriods]));

  const formulas = [];
  let lambdaHomeTotal = 0;
  let lambdaAwayTotal = 0;
  let lambdaHomeCounted = 0;
  let lambdaAwayCounted = 0;

  for (const per of reportPeriods) {
    const periodProjection = computeSinglePeriodProjection({
      periodKey: per,
      homeTeam,
      awayTeam,
      homeStat,
      awayStat,
      neutralGround,
    });

    if (!periodProjection) continue;
    formulas.push(periodProjection);

    if (lambdaPeriods.includes(per)) {
      lambdaHomeTotal += periodProjection.home.lambda;
      lambdaAwayTotal += periodProjection.away.lambda;
      lambdaHomeCounted += 1;
      lambdaAwayCounted += 1;
    }
  }

  if (!lambdaHomeCounted || !lambdaAwayCounted) {
    return {
      lambda: null,
      selectedLambda: null,
      scope,
      reason: "missing-period",
      formulas,
      leagues: { home: homeLeagueName, away: awayLeagueName },
    };
  }

  if (!Number.isFinite(lambdaHomeTotal) || !Number.isFinite(lambdaAwayTotal)) {
    return {
      lambda: null,
      selectedLambda: null,
      scope,
      reason: "invalid-lambda",
      formulas,
      leagues: { home: homeLeagueName, away: awayLeagueName },
    };
  }

  const lambdaTotal = lambdaHomeTotal + lambdaAwayTotal;
  const selectedLambda =
    scope === "home"
      ? lambdaHomeTotal
      : scope === "away"
      ? lambdaAwayTotal
      : lambdaTotal;

  return {
    lambda: { home: lambdaHomeTotal, away: lambdaAwayTotal, total: lambdaTotal },
    selectedLambda,
    scope,
    reason: null,
    leagues: { home: homeLeagueName, away: awayLeagueName },
    formulas,
  };
}
