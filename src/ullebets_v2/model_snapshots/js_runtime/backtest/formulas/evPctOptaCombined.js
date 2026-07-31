import { calibrateEv } from "../math.js";

export function evPctOptaCombined({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeOpta,
  awayOpta,
}) {
  if (!homeOpta?.rank || !awayOpta?.rank || !homeOpta?.rating || !awayOpta?.rating) {
    return { evPctOptaCombined: null };
  }

  const rankDiff = awayOpta.rank - homeOpta.rank;
  const ratingDiff = homeOpta.rating - awayOpta.rating;

  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctOptaCombined: null };

  // Combine both signals.
  // Rank diff of 20 ~ Rating diff of 10?
  // Let's average the adjustment factors.
  const rankFactor = 1 + (rankDiff * 0.002);
  const ratingFactor = 1 + (ratingDiff * 0.01);
  
  const adjustmentFactor = (rankFactor + ratingFactor) / 2;
  const adjustedLambda = baseLambda * adjustmentFactor;

  const modelProb = probabilityOf(adjustedLambda);

  const rawEvPct =
    modelProb != null && oddsValue != null
      ? modelProb * oddsValue * 100 - 100
      : null;

  const evPctValue = rawEvPct != null ? calibrateEv(rawEvPct) : null;

  return {
    evPctOptaCombined: evPctValue,
    optaCombinedLambda: Number(adjustedLambda.toFixed(2)),
    optaCombinedProb: modelProb,
  };
}
