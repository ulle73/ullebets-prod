import { STAT_PATTERNS } from "./constants.js";
import { safeNumber } from "./math.js";

export function normalizeTeamName(name) {
  return String(name || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function teamSlug(name) {
  return normalizeTeamName(name).replace(/\s+/g, "_");
}

function toFeatureSlug(value) {
  if (!value) return "";
  return String(value)
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function extractAllFeaturesFromBlock(block) {
  if (!block?.groups) return null;
  const features = {};
  for (const group of block.groups) {
    for (const row of group.statisticsItems || []) {
      const slug = toFeatureSlug(row.key || row.name);
      if (!slug) continue;
      const homeValue = Number(row.homeValue);
      const awayValue = Number(row.awayValue);
      if (!Number.isFinite(homeValue) || !Number.isFinite(awayValue)) continue;
      const entry = { home: homeValue, away: awayValue, total: homeValue + awayValue };
      features[slug] = entry;
      const alias = slug.replace(/_/g, "");
      if (alias && alias !== slug && !features[alias]) {
        features[alias] = entry;
      }
    }
  }
  return features;
}

function resolveStatisticsBlock(match, periodKey) {
  const details = match?.matchDetails || match?.details || null;
  const statistics = details?.statistics || match?.statistics;
  if (!statistics) return null;
  if (Array.isArray(statistics)) {
    const upper = String(periodKey || "ALL").toUpperCase();
    return (
      statistics.find((entry) => String(entry.period || "").toUpperCase() === upper) ||
      statistics[0] ||
      null
    );
  }
  return statistics;
}

function extractTuple(match, periodKey) {
  const block = resolveStatisticsBlock(match, periodKey);
  if (!block?.groups) return null;

  const stats = {};
  const patterns = Object.entries(STAT_PATTERNS).map(([stat, { keys, names }]) => ({
    stat,
    keys: keys.map((key) => key.toLowerCase()),
    names: names.map((name) => name.toLowerCase()),
  }));

  for (const group of block.groups) {
    for (const row of group.statisticsItems || []) {
      const key = row.key?.toLowerCase();
      const name = row.name?.toLowerCase().trim();
      const matchPattern = patterns.find(
        (pattern) => (key && pattern.keys.includes(key)) || (name && pattern.names.includes(name))
      );
      if (!matchPattern) continue;
      stats[matchPattern.stat] = {
        home: Number(row.homeValue),
        away: Number(row.awayValue),
        total: Number(row.homeValue) + Number(row.awayValue),
      };
    }
  }

  const featureMap = extractAllFeaturesFromBlock(block);
  if (featureMap && Object.keys(featureMap).length) {
    stats.__features = featureMap;
  }

  return stats;
}

export function calcTuple(match, statKey, periodKey) {
  const tuple = extractTuple(match, periodKey);
  if (!tuple) return null;

  const result = {};
  for (const stat in STAT_PATTERNS) {
    if (tuple[stat]) {
      result[stat] = { ...tuple[stat] };
    } else {
      const homeValue = match?.matchDetails?.homeStats?.[stat];
      const awayValue = match?.matchDetails?.awayStats?.[stat];
      if (Number.isFinite(homeValue) && Number.isFinite(awayValue)) {
        result[stat] = {
          home: Number(homeValue),
          away: Number(awayValue),
          total: Number(homeValue) + Number(awayValue),
        };
      }
    }
  }

  if (tuple.__features) {
    result.__features = tuple.__features;
  }

  if (result.freeKicks) {
    const homeBase = safeNumber(result.freeKicks.home);
    const awayBase = safeNumber(result.freeKicks.away);
    const offsides = result.offsides || {};
    const homeOpponentOffsides = safeNumber(offsides.away);
    const awayOpponentOffsides = safeNumber(offsides.home);
    const homeAdjusted = homeBase + homeOpponentOffsides;
    const awayAdjusted = awayBase + awayOpponentOffsides;
    result.freeKicks = {
      home: homeAdjusted,
      away: awayAdjusted,
      total: homeAdjusted + awayAdjusted,
    };
  }

  return result;
}

export function getMatchTimestamp(match) {
  const candidates = [
    match?.timestamp,
    match?.startTimestamp,
    match?.matchTimestamp,
    match?.kickoff,
    match?.matchDetails?.timestamp,
    match?.matchDetails?.startTimestamp,
  ];
  for (const candidate of candidates) {
    const value = Number(candidate);
    if (Number.isFinite(value) && value > 0) {
      return value;
    }
  }
  if (match?.start) {
    const parsed = Date.parse(match.start);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  if (match?.matchDate) {
    const parsed = Date.parse(match.matchDate);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function dedupeMatches(matches) {
  const seen = new Set();
  const result = [];
  for (const match of matches) {
    if (!match) continue;
    const home = teamSlug(match.homeTeamName || match.homeTeam || match.home);
    const away = teamSlug(match.awayTeamName || match.awayTeam || match.away);
    const ts = getMatchTimestamp(match);
    const key = `${home}_${away}_${ts ?? "na"}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(match);
  }
  return result;
}

export function buildTuples({
  homeMatches = [],
  awayMatches = [],
  statKey,
  periodKey,
}) {
  const combined = dedupeMatches([...(homeMatches || []), ...(awayMatches || [])]);
  const tuples = [];
  for (const match of combined) {
    const data = calcTuple(match, statKey, periodKey);
    if (!data || !data[statKey]) continue;
    const meta = { ...match, timestamp: getMatchTimestamp(match) };
    tuples.push({ meta, data });
  }
  tuples.sort((a, b) => {
    const aTs = a.meta.timestamp ?? 0;
    const bTs = b.meta.timestamp ?? 0;
    return bTs - aTs;
  });
  return tuples;
}
