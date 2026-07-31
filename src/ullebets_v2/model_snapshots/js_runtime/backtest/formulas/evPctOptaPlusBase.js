import { calibrateEv } from "../math.js";

export function evPctOptaPlusBase({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeOpta,
  awayOpta,
}) {
  // This formula takes the base probability and averages it with the Opta-derived probability.
  // It assumes we have evPctOptaCombined logic or similar available, or we re-implement it.
  // Let's re-implement a simple Opta adjustment here.

  if (!homeOpta?.rating || !awayOpta?.rating) {
    return { evPctOptaPlusBase: null };
  }

  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctOptaPlusBase: null };

  const ratingDiff = homeOpta.rating - awayOpta.rating;
  const adjustmentFactor = 1 + (ratingDiff * 0.01);
  const optaLambda = baseLambda * adjustmentFactor;
  
  const baseProb = baseResult.prob;
  const optaProb = probabilityOf(optaLambda);

  if (baseProb == null || optaProb == null) return { evPctOptaPlusBase: null };

  // Weighted average: 70% Base, 30% Opta
  const blendedProb = (baseProb * 0.7) + (optaProb * 0.3);

  const rawEvPct =
    blendedProb != null && oddsValue != null
      ? blendedProb * oddsValue * 100 - 100
      : null;

  const evPctValue = rawEvPct != null ? calibrateEv(rawEvPct) : null;

  return {
    evPctOptaPlusBase: evPctValue,
    optaPlusBaseProb: blendedProb,
  };
}
