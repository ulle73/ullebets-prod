export const PHASE1_ML_COMBOS = [
  ["totalShots", "total", "ALL"],
  ["totalShots", "home", "ALL"],
  ["totalShots", "away", "ALL"],
  ["shotsOnGoal", "total", "ALL"],
  ["shotsOnGoal", "home", "ALL"],
  ["shotsOnGoal", "away", "ALL"],
];

const PHASE1_ML_COMBO_KEYS = new Set(
  PHASE1_ML_COMBOS.map(([statKey, scope, period]) => `${statKey}|${scope}|${period}`)
);

export function isPhase1MlCombo(statKey, scope = "total", period = "ALL") {
  return PHASE1_ML_COMBO_KEYS.has(`${statKey}|${scope}|${period}`);
}

export function toPhase1MlFormulaKey(statKey, scope = "total", period = "ALL") {
  if (!isPhase1MlCombo(statKey, scope, period)) {
    return null;
  }
  return `ml_${statKey}_${scope}_${period}`;
}
