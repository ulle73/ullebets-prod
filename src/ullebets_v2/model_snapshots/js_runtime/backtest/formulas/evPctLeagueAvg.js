import { calibrateEv } from "../math.js";

function formatLambda(value) {
  return Number.isFinite(value) ? Number(value.toFixed(2)) : null;
}

export function evPctLeagueAvg({ leagueProjection, oddsValue, implied, probabilityOf }) {
  const leagueLambda = Number.isFinite(leagueProjection?.selectedLambda)
    ? leagueProjection.selectedLambda
    : null;

  const modelProbLeagueAvg =
    leagueLambda != null ? probabilityOf(leagueLambda) : null;

  const rawEvPctLeagueAvg =
    modelProbLeagueAvg != null && oddsValue != null
      ? modelProbLeagueAvg * oddsValue * 100 - 100
      : null;

  const evPctLeagueAvg =
    rawEvPctLeagueAvg != null ? calibrateEv(rawEvPctLeagueAvg) : null;

  const edgePPLeagueAvg =
    modelProbLeagueAvg != null && oddsValue != null
      ? (modelProbLeagueAvg - implied) * 100
      : null;

  const leagueAvg = {
    lambda:
      leagueProjection?.lambda && typeof leagueProjection.lambda === "object"
        ? {
            total: formatLambda(leagueProjection.lambda.total),
            home: formatLambda(leagueProjection.lambda.home),
            away: formatLambda(leagueProjection.lambda.away),
          }
        : null,
    selectedLambda: formatLambda(leagueLambda),
    prob: modelProbLeagueAvg,
    rawEvPct: rawEvPctLeagueAvg,
    evPct: evPctLeagueAvg,
    edgePP: edgePPLeagueAvg,
    details: leagueProjection,
  };

  return {
    leagueAvg,
    modelProbLeagueAvg,
    rawEvPctLeagueAvg,
    evPctLeagueAvg,
    edgePPLeagueAvg,
  };
}
