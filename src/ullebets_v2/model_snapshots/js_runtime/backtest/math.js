export const IMPORTANCE_RANGE = [0.8, 1.2];
export const IMPORTANCE_STEP = 0.05;

export function clamp(min, value, max) {
  return Math.min(Math.max(value, min), max);
}

export function importanceFactor(importance) {
  const [min, max] = IMPORTANCE_RANGE;
  return clamp(min, 1 + IMPORTANCE_STEP * (importance - 5), max);
}

export function weightedMean(values, timestamps, halfLifeDays = 20) {
  if (!Array.isArray(values) || !values.length) return 0;
  const now = Date.now();
  const timeWeights = timestamps.map((ts) => {
    const tsNumber = Number(ts);
    if (!Number.isFinite(tsNumber)) {
      return 1;
    }
    const days = (now - tsNumber) / (1000 * 60 * 60 * 24);
    return Math.exp((-Math.LN2 * days) / halfLifeDays);
  });
  const indexWeight = (idx) => {
    if (idx < 3) return 4;
    if (idx < 6) return 3;
    if (idx < 10) return 2;
    if (idx < 20) return 1;
    return 0.5;
  };
  const weights = values.map((_, i) => (timeWeights[i] ?? 1) * indexWeight(i));
  const sumWeights = weights.reduce((sum, weight) => sum + weight, 0) || 1;
  return (
    values.reduce((sum, value, i) => sum + value * (weights[i] ?? 0), 0) /
    sumWeights
  );
}

export function poissonCdf(k, lambda) {
  const safeLambda = Number.isFinite(lambda) && lambda > 0 ? lambda : 0.0001;
  let sum = 0;
  let term = Math.exp(-safeLambda);
  for (let i = 0; i <= k; i++) {
    if (i > 0) term *= safeLambda / i;
    sum += term;
  }
  return sum;
}

export function blendProb(prob, successes, total, weight = 5) {
  const alpha0 = prob * weight;
  const beta0 = (1 - prob) * weight;
  return (alpha0 + successes) / (alpha0 + beta0 + total);
}

export function calibrateEv(ev) {
  return ev;
}

export function safeNumber(value) {
  return Number.isFinite(value) ? value : 0;
}

export function average(values) {
  const filtered = (values || []).filter((val) => Number.isFinite(val));
  if (!filtered.length) return null;
  return filtered.reduce((sum, val) => sum + val, 0) / filtered.length;
}
