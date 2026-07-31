import { calibrateEv } from "../math.js";

export function evPctOptaRank({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeOpta,
  awayOpta,
}) {
  if (!homeOpta?.rank || !awayOpta?.rank) {
    return { evPctOptaRank: null };
  }

  // Lower rank is better.
  // Simple model: adjust lambda based on rank difference.
  // This is a heuristic and should be tuned.
  const rankDiff = awayOpta.rank - homeOpta.rank; // Positive if home is better (lower rank)
  
  // Example adjustment: 1% increase in lambda for every 10 rank positions difference?
  // Or maybe just adjust the probability directly?
  // Let's try adjusting lambda.
  
  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctOptaRank: null };

  // Heuristic: +0.5% lambda per rank diff unit (capped)
  // If home is rank 1 and away is rank 20, diff is 19.
  // 19 * 0.005 = 0.095 increase in lambda?
  // This is just a starting point for the backtest to evaluate.
  const adjustmentFactor = 1 + (rankDiff * 0.002); 
  const adjustedLambda = baseLambda * adjustmentFactor;

  const modelProb = probabilityOf(adjustedLambda);

  const rawEvPct =
    modelProb != null && oddsValue != null
      ? modelProb * oddsValue * 100 - 100
      : null;

  const evPctValue = rawEvPct != null ? calibrateEv(rawEvPct) : null;

  return {
    evPctOptaRank: evPctValue,
    optaRankLambda: Number(adjustedLambda.toFixed(2)),
    optaRankProb: modelProb,
  };
}
