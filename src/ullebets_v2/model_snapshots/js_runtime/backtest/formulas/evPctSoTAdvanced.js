export function evPctSoTAdvanced({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeBundle,
  awayBundle,
}) {
  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctSoTAdvanced: null };

  const getMetric = (bundle, group, key) => {
    const profile = bundle?.home || bundle?.away;
    const val = profile?.statistics?.[group]?.[key]?.ALL?.value;
    return val ? parseFloat(val) : null;
  };

  const homeBigChances = getMetric(homeBundle, "matchOverview", "bigChanceCreated");
  const awayBigChances = getMetric(awayBundle, "matchOverview", "bigChanceCreated");
  
  const homeTotalShots = getMetric(homeBundle, "matchOverview", "totalShotsOnGoal"); // Note: key might vary, checking previous file
  const awayTotalShots = getMetric(awayBundle, "matchOverview", "totalShotsOnGoal");

  let adjustment = 1;

  // Big Chances Logic: High quality chances -> more SoT
  if (homeBigChances !== null && awayBigChances !== null) {
    const diff = homeBigChances - awayBigChances;
    adjustment += (diff * 0.05); // +5% per big chance diff
  }

  // Volume Logic: More shots -> more SoT (redundant but reinforcing)
  if (homeTotalShots !== null && awayTotalShots !== null) {
    const diff = homeTotalShots - awayTotalShots;
    adjustment += (diff * 0.01);
  }

  const adjustedLambda = baseLambda * adjustment;
  const modelProb = probabilityOf(adjustedLambda);
  
  if (!modelProb) return { evPctSoTAdvanced: null };

  const evPct = (modelProb * oddsValue * 100) - 100;

  return {
    evPctSoTAdvanced: Number(evPct.toFixed(2)),
    sotAdvancedLambda: Number(adjustedLambda.toFixed(2)),
    sotAdvancedProb: Number(modelProb.toFixed(4)),
  };
}
