import { calibrateEv } from "../math.js";

function formatLambda(value) {
  return Number.isFinite(value) ? Number(value.toFixed(2)) : null;
}

export function evPctMultifactor({
  multifactorProjection,
  oddsValue,
  implied,
  probabilityOf,
}) {
  const lambda = Number.isFinite(multifactorProjection?.lambda)
    ? multifactorProjection.lambda
    : null;

  const modelProbMultifactor = lambda != null ? probabilityOf(lambda) : null;

  const rawEvPctMultifactor =
    modelProbMultifactor != null && oddsValue != null
      ? modelProbMultifactor * oddsValue * 100 - 100
      : null;

  const evPctMultifactor =
    rawEvPctMultifactor != null ? calibrateEv(rawEvPctMultifactor) : null;

  const edgePPMultifactor =
    modelProbMultifactor != null && oddsValue != null
      ? (modelProbMultifactor - implied) * 100
      : null;

  const multifactor = {
    lambda: formatLambda(lambda),
    prob: modelProbMultifactor,
    rawEvPct: rawEvPctMultifactor,
    evPct: evPctMultifactor,
    edgePP: edgePPMultifactor,
    details: multifactorProjection,
  };

  return {
    multifactor,
    modelProbMultifactor,
    rawEvPctMultifactor,
    evPctMultifactor,
    edgePPMultifactor,
  };
}
