import { calibrateEv } from "../math.js";

export function evPct({ baseResult, oddsValue, implied }) {
  const rawEvPct =
    oddsValue != null && Number.isFinite(baseResult?.prob)
      ? baseResult.prob * oddsValue * 100 - 100
      : null;
  const evPctValue = rawEvPct != null ? calibrateEv(rawEvPct) : null;
  const legacyEvPct =
    baseResult?.probLegacy != null && oddsValue != null
      ? baseResult.probLegacy * oddsValue * 100 - 100
      : null;

  return {
    modelProb: baseResult?.prob ?? null,
    empiricalProb: baseResult?.empirical ?? null,
    blendedProb: baseResult?.blended ?? null,
    edgePP:
      oddsValue != null && Number.isFinite(baseResult?.prob)
        ? (baseResult.prob - implied) * 100
        : null,
    evPct: evPctValue,
    rawEvPct,
    legacyProb: baseResult?.probLegacy ?? null,
    legacyEvPct,
  };
}
