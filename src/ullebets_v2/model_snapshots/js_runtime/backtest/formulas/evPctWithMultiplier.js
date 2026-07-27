import { calibrateEv } from "../math.js";

export function evPctWithMultiplier({
  baseResult,
  multiplierResult,
  oddsValue,
  implied,
  probabilityOf,
}) {
  const lambdaWithMultiplier =
    Number.isFinite(baseResult?.lambda) && Number.isFinite(multiplierResult?.multiplier)
      ? baseResult.lambda * multiplierResult.multiplier
      : null;

  const modelProbWithMultiplier =
    lambdaWithMultiplier != null ? probabilityOf(lambdaWithMultiplier) : null;

  const rawEvPctWithMultiplier =
    modelProbWithMultiplier != null && oddsValue != null
      ? modelProbWithMultiplier * oddsValue * 100 - 100
      : null;

  const evPctValue =
    rawEvPctWithMultiplier != null ? calibrateEv(rawEvPctWithMultiplier) : null;

  const edgePPWithMultiplier =
    modelProbWithMultiplier != null && oddsValue != null
      ? (modelProbWithMultiplier - implied) * 100
      : null;

  return {
    multiplier: multiplierResult,
    lambdaWithMultiplier:
      lambdaWithMultiplier != null ? Number(lambdaWithMultiplier.toFixed(2)) : null,
    modelProbWithMultiplier,
    edgePPWithMultiplier,
    rawEvPctWithMultiplier,
    evPctWithMultiplier: evPctValue,
  };
}
