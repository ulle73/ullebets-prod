import fs from "node:fs";
import path from "path";
import { fileURLToPath } from "url";
import { calibrateEv } from "../math.js";
import {
  PHASE1_ML_COMBOS,
  buildPhase1MlInput,
  predictTier2Count,
} from "./mlTier2Runtime.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const AVAILABLE_COMBOS = PHASE1_ML_COMBOS;

function getModelPath(statKey, scope, period) {
  return path.join(
    __dirname,
    "../../../machinelearning/models/trained/tier2",
    `${statKey}_${scope}_${period}_stacked.json`
  );
}

function getFormulaName(statKey, scope, period) {
  return `ml_${statKey}_${scope}_${period}`;
}

function readMlTier2Enabled() {
  return process.env.ENABLE_ML_TIER2 === "1";
}

function computeSafeModelResult(context, formulaName, combo) {
  const { statKey, scope, period } = combo;
  const { rawFeatures, formulaPredictions } = buildPhase1MlInput(context);
  const predictedCount = predictTier2Count({
    statKey,
    scope,
    period,
    rawFeatures,
    formulaPredictions,
  });

  if (!Number.isFinite(predictedCount)) {
    return {};
  }

  const modelProb =
    typeof context?.probabilityOf === "function" ? context.probabilityOf(predictedCount) : null;
  const oddsValue = Number(context?.oddsValue);
  const rawEvPct =
    modelProb != null && Number.isFinite(oddsValue) && oddsValue > 0
      ? modelProb * oddsValue * 100 - 100
      : null;
  const evPctValue = rawEvPct != null ? calibrateEv(rawEvPct) : null;

  return {
    [formulaName]: evPctValue,
    [`${formulaName}_prob`]: modelProb,
    [`${formulaName}_raw`]: rawEvPct,
    [`${formulaName}_count`]: predictedCount,
  };
}

function createMLFormula(statKey, scope, period) {
  const formulaName = getFormulaName(statKey, scope, period);

  return function mlTier2Formula(context) {
    const { params } = context || {};
    if (
      !params ||
      params.statKey !== statKey ||
      params.scope !== scope ||
      params.period !== period
    ) {
      return {};
    }

    if (!readMlTier2Enabled()) {
      return {};
    }

    return computeSafeModelResult(context, formulaName, { statKey, scope, period });
  };
}

export function isMlTier2Enabled() {
  return readMlTier2Enabled();
}

export function getAvailableMLFormulas() {
  return AVAILABLE_COMBOS.filter(([statKey, scope, period]) =>
    fs.existsSync(getModelPath(statKey, scope, period))
  );
}

export const ML_FORMULAS = AVAILABLE_COMBOS.map(([statKey, scope, period]) =>
  createMLFormula(statKey, scope, period)
);

export const ml_totalShots_total_ALL = createMLFormula("totalShots", "total", "ALL");
export const ml_totalShots_home_ALL = createMLFormula("totalShots", "home", "ALL");
export const ml_totalShots_away_ALL = createMLFormula("totalShots", "away", "ALL");
export const ml_shotsOnGoal_total_ALL = createMLFormula("shotsOnGoal", "total", "ALL");
export const ml_shotsOnGoal_home_ALL = createMLFormula("shotsOnGoal", "home", "ALL");
export const ml_shotsOnGoal_away_ALL = createMLFormula("shotsOnGoal", "away", "ALL");
