import { average, clamp } from "../math.js";

export function computeMultifactorProjection({ base, leagueProjection, weights = {} }) {
  const components = {};
  let lambda = null;
  let totalWeight = 0;

  const baseLambda = Number.isFinite(base.lambda) ? base.lambda : null;
  const leagueLambda = Number.isFinite(leagueProjection?.selectedLambda)
    ? leagueProjection.selectedLambda
    : null;

  const sampleSize = base.teamTuples?.length || base.statsFor?.length || 0;
  const baseWeight = baseLambda != null ? Math.min(0.75, sampleSize / (sampleSize + 5)) : 0;
  const leagueWeight = leagueLambda != null ? Math.max(0.25, 1 - baseWeight) : 0;
  const overrideBaseWeight =
    weights && Number.isFinite(weights.baseWeight) ? weights.baseWeight : undefined;
  const overrideLeagueWeight =
    weights && Number.isFinite(weights.leagueWeight) ? weights.leagueWeight : undefined;

  const appliedBaseWeight = overrideBaseWeight ?? baseWeight;
  const appliedLeagueWeight = overrideLeagueWeight ?? leagueWeight;

  if (baseLambda != null && appliedBaseWeight > 0) {
    lambda = (lambda ?? 0) + baseLambda * appliedBaseWeight;
    totalWeight += appliedBaseWeight;
    components.base = { lambda: baseLambda, weight: appliedBaseWeight };
  }

  if (leagueLambda != null && appliedLeagueWeight > 0) {
    lambda = (lambda ?? 0) + leagueLambda * appliedLeagueWeight;
    totalWeight += appliedLeagueWeight;
    components.league = { lambda: leagueLambda, weight: appliedLeagueWeight };
  }

  if (!totalWeight) {
    if (baseLambda != null) {
      return { lambda: baseLambda, components: { base: { lambda: baseLambda, weight: 1 } } };
    }
    if (leagueLambda != null) {
      return { lambda: leagueLambda, components: { league: { lambda: leagueLambda, weight: 1 } } };
    }
    return { lambda: null, components: {} };
  }

  lambda /= totalWeight;

  const attackAvg = average(base.statsFor);
  const defenseAvg = average(base.statsAgainst);
  const adjustments = {};

  if (attackAvg != null && defenseAvg != null) {
    const diff = attackAvg - defenseAvg;
    const scale = clamp(-0.3, diff / Math.max(1, attackAvg + defenseAvg), 0.3);
    const delta = scale * lambda;
    if (Number.isFinite(delta) && delta !== 0) {
      lambda += delta;
      adjustments.formDifferential = delta;
    }
  }

  if (Number.isFinite(base.empirical) && Number.isFinite(base.prob)) {
    const bias = clamp(-0.2, base.empirical - base.prob, 0.2);
    const delta = bias * lambda;
    if (Number.isFinite(delta) && delta !== 0) {
      lambda += delta;
      adjustments.empiricalBias = delta;
    }
  }

  if (lambda < 0) {
    lambda = 0;
  }

  components.adjustments = adjustments;
  return { lambda, components };
}
