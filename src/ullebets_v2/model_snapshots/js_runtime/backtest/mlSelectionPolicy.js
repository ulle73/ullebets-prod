import { isPhase1MlCombo, toPhase1MlFormulaKey } from "./mlPhase1Combos.js";

const DEFAULT_ML_SELECTION_MODE = "off";

const INLINE_ML_SELECTION_POLICY = {
  totalShots: {
    total: {
      ALL: "primary",
    },
    home: {
      ALL: "off",
    },
    away: {
      ALL: "primary",
    },
  },
  shotsOnGoal: {
    total: {
      ALL: "off",
    },
    home: {
      ALL: "primary",
    },
    away: {
      ALL: "off",
    },
  },
};

function normalizeMode(value) {
  return value === "primary" ? "primary" : DEFAULT_ML_SELECTION_MODE;
}

export function getMlSelectionMode(statKey, scope = "total", period = "ALL") {
  if (!isPhase1MlCombo(statKey, scope, period)) {
    return DEFAULT_ML_SELECTION_MODE;
  }

  const configured =
    INLINE_ML_SELECTION_POLICY?.[statKey]?.[scope]?.[period] ?? DEFAULT_ML_SELECTION_MODE;
  return normalizeMode(configured);
}

export function resolveMlFormulaKey(statKey, scope = "total", period = "ALL") {
  return toPhase1MlFormulaKey(statKey, scope, period);
}

export function getMlSelectionPolicy(statKey, scope = "total", period = "ALL") {
  return {
    mode: getMlSelectionMode(statKey, scope, period),
    formulaKey: resolveMlFormulaKey(statKey, scope, period),
  };
}
