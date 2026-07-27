import { calibrateEv } from "../math.js";

export function evPctOptaRating({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeOpta,
  awayOpta,
}) {
  if (!homeOpta?.rating || !awayOpta?.rating) {
    return { evPctOptaRating: null };
  }

  // Higher rating is better.
  const ratingDiff = homeOpta.rating - awayOpta.rating; // Positive if home is better

  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctOptaRating: null };

  // Heuristic: Rating is roughly 0-100.
  // Diff of 10 points -> significant advantage.
  // Let's say 10 points = 10% increase in lambda.
  const adjustmentFactor = 1 + (ratingDiff * 0.01);
  const adjustedLambda = baseLambda * adjustmentFactor;

  const modelProb = probabilityOf(adjustedLambda);

  const rawEvPct =
    modelProb != null && oddsValue != null
      ? modelProb * oddsValue * 100 - 100
      : null;

  const evPctValue = rawEvPct != null ? calibrateEv(rawEvPct) : null;

  return {
    evPctOptaRating: evPctValue,
    optaRatingLambda: Number(adjustedLambda.toFixed(2)),
    optaRatingProb: modelProb,
  };
}
