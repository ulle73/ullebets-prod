import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
export { PHASE1_ML_COMBOS } from "../mlPhase1Combos.js";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const TIER2_FORMULA_KEYS = [
  "evPct",
  "evPctLeagueAvg",
  "evPctMultifactor",
  "evPctWithMultiplier",
  "legacyEvPct",
];

const EXTRA_FEATURE_KEYS = [
  "ballPossession",
  "passes",
  "accuratePasses",
  "finalThirdEntries",
  "touchesInOppBox",
  "expectedGoals",
  "bigChanceCreated",
  "bigChanceMissed",
  "bigChanceScored",
  "shotsOffGoal",
  "totalShotsInsideBox",
  "totalShotsOutsideBox",
  "accurateCross",
  "accurateLongBalls",
  "ballRecovery",
  "interceptionWon",
  "dispossessed",
  "blockedScoringAttempt",
  "duelWonPercent",
  "groundDuelsPercentage",
  "aerialDuelsPercentage",
  "cleanSheets",
  "goalsConceded",
  "tackles",
  "clearances",
  "dribbles",
  "dribblesCompleted",
  "touches",
  "duels",
  "groundDuels",
  "aerialDuels",
];

const modelCache = new Map();
const metadataCache = new Map();

function toFiniteNumber(value, fallback = null) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function getModelPath(tier, statKey, scope, period) {
  return path.join(
    __dirname,
    `../../../machinelearning/models/trained/${tier}`,
    `${statKey}_${scope}_${period}_${tier === "tier2" ? "stacked" : "raw"}.json`
  );
}

function getMetadataPath(tier, statKey, scope, period) {
  return path.join(
    __dirname,
    `../../../machinelearning/models/trained/${tier}`,
    `${statKey}_${scope}_${period}_${tier === "tier2" ? "stacked" : "raw"}_metadata.json`
  );
}

export function loadXGBoostRegressor(modelPath) {
  if (modelCache.has(modelPath)) {
    return modelCache.get(modelPath);
  }

  if (!fs.existsSync(modelPath)) {
    modelCache.set(modelPath, null);
    return null;
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(modelPath, "utf8"));
    modelCache.set(modelPath, parsed);
    return parsed;
  } catch (error) {
    console.error(`[mlTier2Runtime] Failed to load model ${modelPath}:`, error.message);
    modelCache.set(modelPath, null);
    return null;
  }
}

function loadModelMetadata(metadataPath) {
  if (metadataCache.has(metadataPath)) {
    return metadataCache.get(metadataPath);
  }

  if (!fs.existsSync(metadataPath)) {
    metadataCache.set(metadataPath, null);
    return null;
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(metadataPath, "utf8"));
    metadataCache.set(metadataPath, parsed);
    return parsed;
  } catch (error) {
    console.error(`[mlTier2Runtime] Failed to load metadata ${metadataPath}:`, error.message);
    metadataCache.set(metadataPath, null);
    return null;
  }
}

export function predictXGBoostRegressor(model, features) {
  if (!model || !Array.isArray(features) || !features.length) {
    return null;
  }

  const learner = model?.learner;
  const trees = learner?.gradient_booster?.model?.trees;
  const baseScore = toFiniteNumber(learner?.learner_model_param?.base_score, 0);

  if (!Array.isArray(trees) || !Number.isFinite(baseScore)) {
    return null;
  }

  let prediction = baseScore;

  for (const tree of trees) {
    let node = 0;

    while (true) {
      const leftChild = tree?.left_children?.[node];
      const rightChild = tree?.right_children?.[node];
      const isLeaf = leftChild === -1 && rightChild === -1;

      if (isLeaf) {
        const leafValue = toFiniteNumber(tree?.base_weights?.[node], 0);
        prediction += leafValue;
        break;
      }

      const featureIndex = Number(tree?.split_indices?.[node]);
      const splitCondition = toFiniteNumber(tree?.split_conditions?.[node], 0);
      const defaultLeft = Boolean(tree?.default_left?.[node]);
      const featureValue = toFiniteNumber(features[featureIndex], Number.NaN);

      if (Number.isNaN(featureValue)) {
        node = defaultLeft ? leftChild : rightChild;
        continue;
      }

      node = featureValue < splitCondition ? leftChild : rightChild;
    }
  }

  return prediction;
}

function predictTier1Count({ statKey, scope, period, rawFeatures }) {
  const model = loadXGBoostRegressor(getModelPath("tier1", statKey, scope, period));
  const metadata = loadModelMetadata(getMetadataPath("tier1", statKey, scope, period));
  if (!model || !Array.isArray(rawFeatures)) {
    return 0;
  }

  const selectedFeatures = Array.isArray(metadata?.selected_features)
    ? metadata.selected_features
    : null;
  const featureVector = selectedFeatures
    ? selectedFeatures.map((index) => toFiniteNumber(rawFeatures[index], 0))
    : rawFeatures;

  return toFiniteNumber(predictXGBoostRegressor(model, featureVector), 0);
}

function buildTier2FeatureVector({ rawFeatures, formulaPredictions, statKey, scope, period }) {
  if (!Array.isArray(rawFeatures) || !rawFeatures.length) {
    return null;
  }

  const safeFormulaPredictions = formulaPredictions && typeof formulaPredictions === "object"
    ? formulaPredictions
    : {};
  const formulaValues = TIER2_FORMULA_KEYS.map((key) =>
    toFiniteNumber(safeFormulaPredictions[key], 0)
  );
  const predictionValues = Object.values(safeFormulaPredictions).filter((value) =>
    Number.isFinite(Number(value))
  );

  let consensus = [0, 0, 0, 0, 0];
  if (predictionValues.length) {
    const numericPredictions = predictionValues.map((value) => Number(value));
    const mean =
      numericPredictions.reduce((sum, value) => sum + value, 0) / numericPredictions.length;
    const variance =
      numericPredictions.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
      numericPredictions.length;
    const sorted = [...numericPredictions].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)] ?? 0;

    consensus = [
      Math.sqrt(variance),
      Math.max(...numericPredictions) - Math.min(...numericPredictions),
      Math.max(...numericPredictions),
      Math.min(...numericPredictions),
      median,
    ];
  }

  const tier1Prediction = predictTier1Count({
    statKey,
    scope,
    period,
    rawFeatures,
  });

  return [...rawFeatures, ...formulaValues, ...consensus, tier1Prediction];
}

export function predictTier2Count({ statKey, scope, period, rawFeatures, formulaPredictions }) {
  const model = loadXGBoostRegressor(getModelPath("tier2", statKey, scope, period));
  const features = buildTier2FeatureVector({
    rawFeatures,
    formulaPredictions,
    statKey,
    scope,
    period,
  });

  if (!model || !features) {
    return null;
  }

  return predictXGBoostRegressor(model, features);
}

function normalizeStatValue(value, defaultFallback = 0) {
  return toFiniteNumber(value, defaultFallback);
}

function readProfileStatNode(profile, orientation, statKey, period = "ALL") {
  return (
    profile?.statistics?.[orientation]?.[statKey]?.[period] ??
    profile?.statistics?.[statKey]?.[period] ??
    null
  );
}

function readProfileStatValue(profile, orientation, statKey, period = "ALL") {
  const node = readProfileStatNode(profile, orientation, statKey, period);
  return normalizeStatValue(node?.value ?? node?.Value ?? node, 0);
}

function readProfileStatRank(profile, orientation, statKey, period = "ALL") {
  const node = readProfileStatNode(profile, orientation, statKey, period);
  return normalizeStatValue(node?.rank, 50);
}

function readSpecialPercentage(profile, metric) {
  const raw =
    profile?.specials?.firstGoal?.[metric] ??
    profile?.firstGoal?.[metric] ??
    null;
  const numeric = toFiniteNumber(raw, null);
  if (!Number.isFinite(numeric)) {
    return 50;
  }
  return numeric <= 1 ? numeric * 100 : numeric;
}

function readSpecialPerMinute(profile, state) {
  return normalizeStatValue(
    profile?.specials?.shotsPerMinute?.for?.[state] ??
      profile?.shotsPerMinute?.[state] ??
      null,
    0
  );
}

function readShotsPerTenMinuteAverage(profile) {
  const explicit =
    profile?.specials?.shotsPerTenMinutes?.for?.avg ??
    profile?.shotsPerTenMinutes?.avg ??
    null;
  if (Number.isFinite(Number(explicit))) {
    return Number(explicit);
  }

  const values = Object.values(profile?.specials?.shotsPerTenMinutes?.for ?? {}).filter((value) =>
    Number.isFinite(Number(value))
  );
  if (!values.length) {
    return 0;
  }
  return values.reduce((sum, value) => sum + Number(value), 0) / values.length;
}

function extractMatchStatValue(match, statKey, teamRole, mode = "for", period = "ALL") {
  const sections = Array.isArray(match?.matchDetails?.statistics)
    ? match.matchDetails.statistics
    : Object.values(match?.matchDetails?.statistics ?? {});
  const periodSection =
    sections.find((section) => section?.period === period) ??
    sections.find((section) => section?.period === "ALL") ??
    null;

  if (periodSection?.groups) {
    for (const group of periodSection.groups) {
      const item = group?.statisticsItems?.find((entry) => entry?.key === statKey);
      if (!item) continue;

      const forValue =
        teamRole === "home" ? item?.homeValue ?? item?.home : item?.awayValue ?? item?.away;
      const againstValue =
        teamRole === "home" ? item?.awayValue ?? item?.away : item?.homeValue ?? item?.home;
      return normalizeStatValue(mode === "for" ? forValue : againstValue, 0);
    }
  }

  if (period === "ALL" && match?.teamStats?.[statKey] != null) {
    return normalizeStatValue(match.teamStats[statKey], 0);
  }

  return 0;
}

function calculateRuntimeWMA(matches, statKey, window, beforeDate, teamRole, mode = "for", period = "ALL") {
  if (!Array.isArray(matches) || !matches.length) {
    return 0;
  }

  const relevantMatches = matches
    .filter((match) => {
      const rawDate = match?.date ?? match?.matchDate ?? match?.timestamp;
      const matchDate = new Date(rawDate);
      return Number.isFinite(matchDate.getTime()) && matchDate < beforeDate;
    })
    .slice(0, window);

  if (!relevantMatches.length) {
    return 0;
  }

  let weightedSum = 0;
  let totalWeight = 0;

  for (let index = 0; index < relevantMatches.length; index += 1) {
    const weight = 0.9 ** index;
    const value = extractMatchStatValue(
      relevantMatches[index],
      statKey,
      teamRole,
      mode,
      period
    );
    weightedSum += value * weight;
    totalWeight += weight;
  }

  return totalWeight > 0 ? weightedSum / totalWeight : 0;
}

function buildRawFeaturesFromContext(context) {
  const params = context?.params ?? {};
  const statKey = params.statKey;
  const scope = params.scope;
  const period = params.period ?? "ALL";
  const lineValue = toFiniteNumber(params.line, 0);
  const overOdds = toFiniteNumber(context?.oddsValue, 0);
  const underOdds = toFiniteNumber(params.underOdds, 0);
  const impliedOver = overOdds > 0 ? 1 / overOdds : 0;
  const impliedUnder = underOdds > 0 ? 1 / underOdds : 0;
  const margin =
    impliedOver > 0 && impliedUnder > 0 ? impliedOver + impliedUnder - 1 : 0;
  const beforeDate = new Date(params.matchDate ?? params.date ?? Date.now());
  const homeProfile = context?.homeBundle?.home ?? null;
  const awayProfile = context?.awayBundle?.away ?? null;
  const homeMatches = Array.isArray(context?.homeMatchesRaw) ? context.homeMatchesRaw : [];
  const awayMatches = Array.isArray(context?.awayMatchesRaw) ? context.awayMatchesRaw : [];
  const safeFormulaResults =
    context?.formulaResults && typeof context.formulaResults === "object"
      ? context.formulaResults
      : {};
  const excludeShotFeatures = statKey === "totalShots";

  const rawFeatures = [];

  rawFeatures.push(lineValue, overOdds, impliedOver, underOdds, impliedUnder, margin);

  rawFeatures.push(toFiniteNumber(context?.homeOpta?.optaRank, 100));
  rawFeatures.push(toFiniteNumber(context?.homeOpta?.optaRating, 80));
  rawFeatures.push(toFiniteNumber(context?.awayOpta?.optaRank, 100));
  rawFeatures.push(toFiniteNumber(context?.awayOpta?.optaRating, 80));
  rawFeatures.push(
    toFiniteNumber(context?.homeOpta?.optaRank, 100) -
      toFiniteNumber(context?.awayOpta?.optaRank, 100)
  );
  rawFeatures.push(
    toFiniteNumber(context?.homeOpta?.optaRating, 80) -
      toFiniteNumber(context?.awayOpta?.optaRating, 80)
  );

  rawFeatures.push(readProfileStatValue(homeProfile, "for", statKey, period));
  rawFeatures.push(readProfileStatRank(homeProfile, "for", statKey, period));
  rawFeatures.push(readProfileStatValue(awayProfile, "for", statKey, period));
  rawFeatures.push(readProfileStatRank(awayProfile, "for", statKey, period));

  rawFeatures.push(toFiniteNumber(homeProfile?.rankFor, 50));
  rawFeatures.push(toFiniteNumber(homeProfile?.rankAgainst, 50));
  rawFeatures.push(toFiniteNumber(awayProfile?.rankFor, 50));
  rawFeatures.push(toFiniteNumber(awayProfile?.rankAgainst, 50));
  rawFeatures.push(
    toFiniteNumber(homeProfile?.rankFor, 50) / Math.max(1, toFiniteNumber(awayProfile?.rankAgainst, 50))
  );

  rawFeatures.push(calculateRuntimeWMA(homeMatches, statKey, 5, beforeDate, "home", "for", period));
  rawFeatures.push(calculateRuntimeWMA(homeMatches, statKey, 15, beforeDate, "home", "for", period));
  rawFeatures.push(calculateRuntimeWMA(homeMatches, statKey, 30, beforeDate, "home", "for", period));
  rawFeatures.push(calculateRuntimeWMA(awayMatches, statKey, 5, beforeDate, "away", "for", period));
  rawFeatures.push(calculateRuntimeWMA(awayMatches, statKey, 15, beforeDate, "away", "for", period));
  rawFeatures.push(calculateRuntimeWMA(awayMatches, statKey, 30, beforeDate, "away", "for", period));
  rawFeatures.push(calculateRuntimeWMA(homeMatches, statKey, 5, beforeDate, "home", "against", period));
  rawFeatures.push(calculateRuntimeWMA(homeMatches, statKey, 15, beforeDate, "home", "against", period));
  rawFeatures.push(calculateRuntimeWMA(homeMatches, statKey, 30, beforeDate, "home", "against", period));
  rawFeatures.push(calculateRuntimeWMA(awayMatches, statKey, 5, beforeDate, "away", "against", period));
  rawFeatures.push(calculateRuntimeWMA(awayMatches, statKey, 15, beforeDate, "away", "against", period));
  rawFeatures.push(calculateRuntimeWMA(awayMatches, statKey, 30, beforeDate, "away", "against", period));

  const relevantPeriods =
    period === "1ST" ? ["1ST"] : period === "2ND" ? ["1ST", "2ND"] : ["ALL"];
  for (const relevantPeriod of relevantPeriods) {
    rawFeatures.push(readProfileStatValue(homeProfile, "for", statKey, relevantPeriod));
    rawFeatures.push(readProfileStatRank(homeProfile, "for", statKey, relevantPeriod));
    rawFeatures.push(readProfileStatValue(homeProfile, "against", statKey, relevantPeriod));
    rawFeatures.push(readProfileStatRank(homeProfile, "against", statKey, relevantPeriod));
    rawFeatures.push(readProfileStatValue(awayProfile, "for", statKey, relevantPeriod));
    rawFeatures.push(readProfileStatRank(awayProfile, "for", statKey, relevantPeriod));
    rawFeatures.push(readProfileStatValue(awayProfile, "against", statKey, relevantPeriod));
    rawFeatures.push(readProfileStatRank(awayProfile, "against", statKey, relevantPeriod));
  }
  if (relevantPeriods.length === 1) {
    rawFeatures.push(0, 0, 0, 0, 0, 0, 0, 0);
  }

  rawFeatures.push(readSpecialPercentage(homeProfile, "scoreFirstPercentage"));
  rawFeatures.push(readSpecialPercentage(awayProfile, "scoreFirstPercentage"));
  rawFeatures.push(
    readSpecialPercentage(homeProfile, "scoreFirstPercentage") -
      readSpecialPercentage(awayProfile, "scoreFirstPercentage")
  );

  rawFeatures.push(readSpecialPerMinute(homeProfile, "leading"));
  rawFeatures.push(readSpecialPerMinute(homeProfile, "trailing"));
  rawFeatures.push(readSpecialPerMinute(homeProfile, "tied"));
  rawFeatures.push(readSpecialPerMinute(awayProfile, "leading"));
  rawFeatures.push(readSpecialPerMinute(awayProfile, "trailing"));
  rawFeatures.push(readSpecialPerMinute(awayProfile, "tied"));
  rawFeatures.push(readShotsPerTenMinuteAverage(homeProfile));
  rawFeatures.push(readShotsPerTenMinuteAverage(awayProfile));

  for (const key of EXTRA_FEATURE_KEYS) {
    const isShotLeak = excludeShotFeatures && key.toLowerCase().includes("shot");
    rawFeatures.push(isShotLeak ? 0 : readProfileStatValue(homeProfile, "for", key, "ALL"));
    rawFeatures.push(isShotLeak ? 0 : readProfileStatValue(awayProfile, "for", key, "ALL"));
    rawFeatures.push(isShotLeak ? 0 : readProfileStatValue(homeProfile, "against", key, "ALL"));
    rawFeatures.push(isShotLeak ? 0 : readProfileStatValue(awayProfile, "against", key, "ALL"));
  }

  rawFeatures.push(overOdds > 0 ? 0 : 1);
  rawFeatures.push(1);
  rawFeatures.push(0);

  rawFeatures.push(toFiniteNumber(safeFormulaResults.evPctMultifactor, 0));
  rawFeatures.push(toFiniteNumber(safeFormulaResults.evPctUniversalOptimized, 0));
  rawFeatures.push(toFiniteNumber(safeFormulaResults.evPctOptaCombined, 0));
  rawFeatures.push(toFiniteNumber(safeFormulaResults.evPctLeagueAvg, 0));
  rawFeatures.push(toFiniteNumber(safeFormulaResults.evPctOptaRating, 0));

  return rawFeatures;
}

export function buildPhase1MlInput(context) {
  if (context?.mlTier2Input?.rawFeatures) {
    return {
      rawFeatures: context.mlTier2Input.rawFeatures,
      formulaPredictions: context.mlTier2Input.formulaPredictions ?? {},
    };
  }

  const rawFeatures = buildRawFeaturesFromContext(context);
  const formulaPredictions = TIER2_FORMULA_KEYS.reduce((acc, key) => {
    acc[key] = toFiniteNumber(context?.formulaResults?.[key], 0);
    return acc;
  }, {});

  return { rawFeatures, formulaPredictions };
}
