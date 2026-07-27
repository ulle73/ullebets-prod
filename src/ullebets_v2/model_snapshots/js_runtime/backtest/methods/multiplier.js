import { average, clamp } from "../math.js";
import { teamSlug } from "../tuples.js";

function buildFeatureBreakdown({ tuples, homeSlug, awaySlug }) {
  const accumulator = new Map();

  for (const tuple of tuples) {
    const features = tuple.data.__features;
    if (!features || typeof features !== "object") continue;

    const homeIsHome = teamSlug(tuple.meta.homeTeamName) === homeSlug;
    const awayIsAway = teamSlug(tuple.meta.awayTeamName) === awaySlug;
    const homeIsAway = teamSlug(tuple.meta.awayTeamName) === homeSlug;
    const awayIsHome = teamSlug(tuple.meta.homeTeamName) === awaySlug;

    const teamKey = homeIsHome || homeIsAway ? homeSlug : awayIsHome || awayIsAway ? awaySlug : null;
    if (!teamKey) continue;

    const side =
      homeIsHome || awayIsHome
        ? "home"
        : homeIsAway || awayIsAway
        ? "away"
        : null;

    if (!side) continue;

    for (const [key, value] of Object.entries(features)) {
      const entry = value && typeof value === "object" ? value : null;
      if (!entry) continue;
      const teamValue = Number(entry[side]);
      if (!Number.isFinite(teamValue)) continue;
      const baseline = Number.isFinite(entry.total) ? entry.total / 2 : null;
      const diff = baseline != null ? teamValue - baseline : teamValue;
      const agg = accumulator.get(key) || { sum: 0, count: 0 };
      agg.sum += diff;
      agg.count += 1;
      accumulator.set(key, agg);
    }
  }

  const breakdown = {};
  for (const [key, { sum, count }] of accumulator.entries()) {
    if (!count) continue;
    const score = sum / count;
    if (!Number.isFinite(score)) continue;
    if (Math.abs(score) < 0.01) continue;
    breakdown[key] = { score };
  }
  return breakdown;
}

function buildTeamStrength(base, lambda) {
  const attackAvg = average(base.statsFor);
  const defenseAvg = average(base.statsAgainst);
  const strength = {};
  if (Number.isFinite(lambda) && attackAvg != null) {
    const delta = attackAvg - lambda;
    if (Math.abs(delta) >= 0.01) {
      strength.attack = delta;
    }
  }
  if (Number.isFinite(lambda) && defenseAvg != null) {
    const delta = lambda - defenseAvg;
    if (Math.abs(delta) >= 0.01) {
      strength.defense = delta;
    }
  }
  return strength;
}

export function computeMultiplierProjection({ base, tuples, homeSlug, awaySlug }) {
  const ratio = base.prob > 0 ? base.blended / base.prob : 1;
  const rawMultiplier = Number.isFinite(ratio) && ratio > 0 ? ratio : 1;
  const multiplier = clamp(0.6, rawMultiplier, 1.4);
  const rawScore = multiplier - 1;

  const featureBreakdown = buildFeatureBreakdown({ tuples, homeSlug, awaySlug });
  const teamStrength = buildTeamStrength(base, base.lambda);

  return {
    multiplier,
    rawScore,
    teamStrength,
    featureBreakdown,
  };
}
