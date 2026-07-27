import { calibrateEv } from "../math.js";

export function evPctOptaPlusLeagueAvg({
  leagueProjection,
  oddsValue,
  implied,
  probabilityOf,
  homeOpta,
  awayOpta,
}) {
  if (!homeOpta?.rating || !awayOpta?.rating) {
    return { evPctOptaPlusLeagueAvg: null };
  }

  const leagueLambda = leagueProjection?.selectedLambda;
  if (!Number.isFinite(leagueLambda)) return { evPctOptaPlusLeagueAvg: null };

  const ratingDiff = homeOpta.rating - awayOpta.rating;
  const adjustmentFactor = 1 + (ratingDiff * 0.01);
  const optaLambda = leagueLambda * adjustmentFactor;
  
  const leagueProb = probabilityOf(leagueLambda);
  const optaProb = probabilityOf(optaLambda);

  if (leagueProb == null || optaProb == null) return { evPctOptaPlusLeagueAvg: null };

  // Weighted average: 50% League, 50% Opta
  const blendedProb = (leagueProb * 0.5) + (optaProb * 0.5);

  const rawEvPct =
    blendedProb != null && oddsValue != null
      ? blendedProb * oddsValue * 100 - 100
      : null;

  const evPctValue = rawEvPct != null ? calibrateEv(rawEvPct) : null;

  return {
    evPctOptaPlusLeagueAvg: evPctValue,
    optaPlusLeagueAvgProb: blendedProb,
  };
}
