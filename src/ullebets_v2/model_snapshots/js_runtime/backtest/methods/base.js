import {
  blendProb,
  importanceFactor,
  poissonCdf,
  weightedMean,
} from "../math.js";
import { teamSlug, getMatchTimestamp } from "../tuples.js";

function lambdaWeighted(
  homeHome,
  awayAway,
  homeAgainst,
  awayAgainst,
  homeImportance,
  awayImportance,
  statKey
) {
  const gfH = weightedMean(
    homeHome.map((tuple) => tuple.data[statKey]?.home || 0),
    homeHome.map((tuple) => getMatchTimestamp(tuple.meta))
  );
  const gaH = weightedMean(
    homeAgainst.map((tuple) => tuple.data[statKey]?.away || 0),
    homeAgainst.map((tuple) => getMatchTimestamp(tuple.meta))
  );
  const gfA = weightedMean(
    awayAway.map((tuple) => tuple.data[statKey]?.away || 0),
    awayAway.map((tuple) => getMatchTimestamp(tuple.meta))
  );
  const gaA = weightedMean(
    awayAgainst.map((tuple) => tuple.data[statKey]?.home || 0),
    awayAgainst.map((tuple) => getMatchTimestamp(tuple.meta))
  );
  const homeFactor = importanceFactor(homeImportance);
  const awayFactor = importanceFactor(awayImportance);
  const gfHAdj = gfH * homeFactor;
  const gaHAdj = gaH / homeFactor;
  const gfAAdj = gfA * awayFactor;
  const gaAAdj = gaA / awayFactor;
  return 0.6 * gfHAdj + 0.4 * gaAAdj + 0.6 * gfAAdj + 0.4 * gaHAdj;
}

function lambdaBasic(
  homeHome,
  awayAway,
  homeAgainst,
  awayAgainst,
  homeImportance,
  awayImportance,
  statKey
) {
  const mean = (values) =>
    values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
  const gfH = mean(homeHome.map((tuple) => tuple.data[statKey]?.home || 0));
  const gaH = mean(homeAgainst.map((tuple) => tuple.data[statKey]?.away || 0));
  const gfA = mean(awayAway.map((tuple) => tuple.data[statKey]?.away || 0));
  const gaA = mean(awayAgainst.map((tuple) => tuple.data[statKey]?.home || 0));
  const homeFactor = importanceFactor(homeImportance);
  const awayFactor = importanceFactor(awayImportance);
  const gfHAdj = gfH * homeFactor;
  const gaHAdj = gaH / homeFactor;
  const gfAAdj = gfA * awayFactor;
  const gaAAdj = gaA / awayFactor;
  return 0.6 * gfHAdj + 0.4 * gaAAdj + 0.6 * gfAAdj + 0.4 * gaHAdj;
}

function sliceForm(list, limit) {
  if (!Number.isFinite(limit) || limit <= 0 || limit === Infinity) return list;
  return list.slice(0, limit);
}

function mapTimestamps(tuples) {
  return tuples.map((tuple) => getMatchTimestamp(tuple.meta));
}

export function computeBaseProjection({
  tuples,
  statKey,
  scope,
  over,
  line,
  formLimit,
  homeSlug,
  awaySlug,
  homeImportance,
  awayImportance,
  neutralGround,
  blendWeight,
}) {
  const blendWeightValue = Number.isFinite(blendWeight) ? blendWeight : 5;
  const OVER = Boolean(over);
  const LINE = Number(line);

  let statsFor = [];
  let statsAgainst = [];
  let teamTuples = [];
  let opponentTuples = [];
  let hitsOver = 0;
  let hitsUnder = 0;
  let hitsExact = 0;
  let hitsAgainst = 0;
  let empirical = 0;
  let blended = 0;
  let lambda = 0;
  let lambdaLegacy = 0;
  let prob = 0;
  let probLegacy = 0;
  let meanFor = 0;
  let meanAgainst = 0;

  if (scope === "total") {
    const homeSelector = neutralGround
      ? (tuple) => teamSlug(tuple.meta.awayTeamName) === homeSlug
      : (tuple) => teamSlug(tuple.meta.homeTeamName) === homeSlug;
    const awaySelector = (tuple) => teamSlug(tuple.meta.awayTeamName) === awaySlug;

    const homeHome = tuples.filter(homeSelector);
    const awayAway = tuples.filter(awaySelector);
    const homeAgainst = homeHome;
    const awayAgainst = awayAway;

    lambda = lambdaWeighted(
      homeHome,
      awayAway,
      homeAgainst,
      awayAgainst,
      homeImportance,
      awayImportance,
      statKey
    );
    lambdaLegacy = lambdaBasic(
      homeHome,
      awayAway,
      homeAgainst,
      awayAgainst,
      homeImportance,
      awayImportance,
      statKey
    );

    const k = OVER ? Math.max(-1, Math.ceil(LINE) - 1) : Math.floor(LINE);
    const cdf = poissonCdf(k, lambda);
    prob = Math.min(1, Math.max(0, OVER ? 1 - cdf : cdf));
    const cdfLegacy = poissonCdf(k, lambdaLegacy);
    probLegacy = Math.min(1, Math.max(0, OVER ? 1 - cdfLegacy : cdfLegacy));

    const baselineValues = tuples
      .map((tuple) => tuple.data[statKey]?.total)
      .filter((value) => Number.isFinite(value));

    hitsOver = baselineValues.filter((value) => value > LINE).length;
    hitsUnder = baselineValues.filter((value) => value < LINE).length;
    hitsExact = baselineValues.filter((value) => value === LINE).length;
    const hitsFor = OVER ? hitsOver : hitsUnder;
    const baselineCount = baselineValues.length;
    hitsAgainst = baselineCount - hitsFor - hitsExact;
    empirical = baselineCount ? hitsFor / baselineCount : 0;
    blended = blendProb(prob, hitsFor, baselineCount, blendWeightValue);

    statsFor = baselineValues;
    statsAgainst = [];
    teamTuples = new Array(baselineCount).fill(null);
    opponentTuples = [];
  } else {
    const formLimitedTuples = (selector) =>
      sliceForm(
        tuples.filter(selector),
        Number.isFinite(formLimit) ? formLimit : Infinity
      );

    const teamSelector = neutralGround
      ? (tuple) =>
          teamSlug(tuple.meta.awayTeamName) === (scope === "home" ? homeSlug : awaySlug)
      : scope === "home"
      ? (tuple) => teamSlug(tuple.meta.homeTeamName) === homeSlug
      : (tuple) => teamSlug(tuple.meta.awayTeamName) === awaySlug;

    const opponentSelector = neutralGround
      ? (tuple) =>
          teamSlug(tuple.meta.awayTeamName) === (scope === "home" ? awaySlug : homeSlug)
      : scope === "home"
      ? (tuple) => teamSlug(tuple.meta.awayTeamName) === awaySlug
      : (tuple) => teamSlug(tuple.meta.homeTeamName) === homeSlug;

    teamTuples = formLimitedTuples(teamSelector);
    opponentTuples = formLimitedTuples(opponentSelector);

    statsFor = teamTuples
      .map((tuple) => {
        if (scope === "home") {
          return neutralGround ? tuple.data[statKey]?.away : tuple.data[statKey]?.home;
        }
        return tuple.data[statKey]?.away;
      })
      .filter((value) => Number.isFinite(value));

    const opponentSlug = scope === "home" ? awaySlug : homeSlug;
    statsAgainst = opponentTuples
      .map((tuple) => {
        const stat = tuple.data[statKey];
        if (!stat) return undefined;
        const opponentIsHome = teamSlug(tuple.meta.homeTeamName) === opponentSlug;
        return opponentIsHome ? stat.away : stat.home;
      })
      .filter((value) => Number.isFinite(value));

    hitsOver = statsFor.filter((value) => value > LINE).length;
    hitsUnder = statsFor.filter((value) => value < LINE).length;
    hitsExact = statsFor.filter((value) => value === LINE).length;
    const hitsFor = OVER ? hitsOver : hitsUnder;
    hitsAgainst = statsAgainst.filter((value) => (OVER ? value > LINE : value < LINE)).length;

    const meanForBasic =
      statsFor.length > 0
        ? statsFor.reduce((sum, value) => sum + value, 0) / statsFor.length
        : 0;
    const meanAgainstBasic =
      statsAgainst.length > 0
        ? statsAgainst.reduce((sum, value) => sum + value, 0) / statsAgainst.length
        : 0;

    meanFor =
      statsFor.length > 0
        ? weightedMean(statsFor, mapTimestamps(teamTuples))
        : 0;
    meanAgainst =
      statsAgainst.length > 0
        ? weightedMean(statsAgainst, mapTimestamps(opponentTuples))
        : 0;

    const homeFactor = importanceFactor(homeImportance);
    const awayFactor = importanceFactor(awayImportance);
    let meanForLegacy = meanForBasic;
    let meanAgainstLegacy = meanAgainstBasic;

    if (scope === "home") {
      meanFor *= homeFactor;
      meanAgainst /= awayFactor || 1;
      meanForLegacy *= homeFactor;
      meanAgainstLegacy /= awayFactor || 1;
    } else if (scope === "away") {
      meanFor *= awayFactor;
      meanAgainst /= homeFactor || 1;
      meanForLegacy *= awayFactor;
      meanAgainstLegacy /= homeFactor || 1;
    }

    lambda = (meanFor + meanAgainst) / 2;
    lambdaLegacy = (meanForLegacy + meanAgainstLegacy) / 2;

    const k = OVER ? Math.max(-1, Math.ceil(LINE) - 1) : Math.floor(LINE);
    const cdf = poissonCdf(k, lambda);
    prob = Math.min(1, Math.max(0, OVER ? 1 - cdf : cdf));
    const cdfLegacy = poissonCdf(k, lambdaLegacy);
    probLegacy = Math.min(1, Math.max(0, OVER ? 1 - cdfLegacy : cdfLegacy));

    const sampleSize = teamTuples.length;
    empirical = sampleSize ? hitsFor / sampleSize : 0;
    blended = blendProb(prob, hitsFor, sampleSize, blendWeightValue);
  }

  return {
    tuples,
    teamTuples,
    opponentTuples,
    statsFor,
    statsAgainst,
    hits: {
      over: hitsOver,
      under: hitsUnder,
      exact: hitsExact,
      against: hitsAgainst,
    },
    empirical,
    blended,
    lambda,
    lambdaLegacy,
    prob,
    probLegacy,
    meanFor,
    meanAgainst,
  };
}
