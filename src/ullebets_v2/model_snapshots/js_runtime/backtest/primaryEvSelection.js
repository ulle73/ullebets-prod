import { getFormulaConfig } from "./formulaConfig.js";
import { getMlSelectionMode, resolveMlFormulaKey } from "./mlSelectionPolicy.js";

export const FORMULA_VALUE_KEYS = {
  base: "evPct",
  leagueAvg: "evPctLeagueAvg",
  multiplier: "evPctWithMultiplier",
  multifactor: "evPctMultifactor",
  universalOptimized: "evPctUniversalOptimized",
  optaCombined: "evPctOptaCombined",
  optaPlusBase: "evPctOptaPlusBase",
  legacy: "legacyEvPct",
};

export const LIVE_FORMULA_PRIORITY = [
  "universalOptimized",
  "multiplier",
  "multifactor",
  "optaCombined",
  "optaPlusBase",
  "leagueAvg",
  "base",
  "legacy",
];

export const RESEARCH_FORMULA_PRIORITY = [
  "base",
  "leagueAvg",
  "multiplier",
  "multifactor",
  "legacy",
];

const VALUE_KEY_TO_FORMULA_KEY = Object.fromEntries(
  Object.entries(FORMULA_VALUE_KEYS).map(([formulaKey, valueKey]) => [valueKey, formulaKey])
);

function toFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function resolveFormulaValueKey(formulaKey) {
  if (!formulaKey) return null;
  if (String(formulaKey).startsWith("ml_")) {
    return String(formulaKey);
  }
  return FORMULA_VALUE_KEYS[formulaKey] || null;
}

export function getConfiguredFormulaOrder(
  statKey,
  fallbackPriority = LIVE_FORMULA_PRIORITY
) {
  const config = getFormulaConfig(statKey);
  const display = Array.isArray(config?.display) ? config.display : [];
  return [...new Set([...display, ...fallbackPriority])];
}

export function getPrimaryValueKeyOrder({
  statKey,
  scope = "total",
  period = "ALL",
  fallbackPriority = LIVE_FORMULA_PRIORITY,
  mlMode = null,
}) {
  const configuredOrder = getConfiguredFormulaOrder(statKey, fallbackPriority)
    .map((formulaKey) => resolveFormulaValueKey(formulaKey))
    .filter(Boolean);

  const resolvedMlMode = mlMode ?? getMlSelectionMode(statKey, scope, period);
  const mlValueKey =
    resolvedMlMode === "primary" ? resolveMlFormulaKey(statKey, scope, period) : null;

  if (!mlValueKey) {
    return configuredOrder;
  }

  return [mlValueKey, ...configuredOrder.filter((valueKey) => valueKey !== mlValueKey)];
}

export function pickPrimaryEvSelection({
  evDetails,
  statKey,
  scope = "total",
  period = "ALL",
  fallbackPriority = LIVE_FORMULA_PRIORITY,
  mlMode = null,
}) {
  const source = evDetails && typeof evDetails === "object" ? evDetails : {};
  const order = getPrimaryValueKeyOrder({
    statKey,
    scope,
    period,
    fallbackPriority,
    mlMode,
  });

  for (const valueKey of order) {
    const evPct = toFiniteNumber(source[valueKey]);
    if (evPct == null) continue;
    return {
      formulaKey: VALUE_KEY_TO_FORMULA_KEY[valueKey] || valueKey,
      valueKey,
      evPct,
    };
  }

  for (const [valueKey, rawValue] of Object.entries(source)) {
    const evPct = toFiniteNumber(rawValue);
    if (evPct == null) continue;
    return {
      formulaKey: VALUE_KEY_TO_FORMULA_KEY[valueKey] || valueKey,
      valueKey,
      evPct,
    };
  }

  return {
    formulaKey: null,
    valueKey: null,
    evPct: null,
  };
}
