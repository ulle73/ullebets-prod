export function evPctThrowInsAdvanced({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeBundle,
  awayBundle,
}) {
  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctThrowInsAdvanced: null };

  const getMetric = (bundle, group, key) => {
    const profile = bundle?.home || bundle?.away;
    const val = profile?.statistics?.[group]?.[key]?.ALL?.value;
    return val ? parseFloat(val) : null;
  };

  const homeClearances = getMetric(homeBundle, "defending", "totalClearance");
  const awayClearances = getMetric(awayBundle, "defending", "totalClearance");
  
  const homeInterceptions = getMetric(homeBundle, "defending", "interceptionWon");
  const awayInterceptions = getMetric(awayBundle, "defending", "interceptionWon");

  let adjustment = 1;

  // Chaotic Game Logic: High clearances + interceptions -> messy game -> more throw-ins
  if (homeClearances !== null && awayClearances !== null) {
    const totalClearances = homeClearances + awayClearances;
    if (totalClearances > 40) adjustment += 0.1; // High clearance game
  }

  if (homeInterceptions !== null && awayInterceptions !== null) {
    const totalInterceptions = homeInterceptions + awayInterceptions;
    if (totalInterceptions > 20) adjustment += 0.05;
  }

  const adjustedLambda = baseLambda * adjustment;
  const modelProb = probabilityOf(adjustedLambda);
  
  if (!modelProb) return { evPctThrowInsAdvanced: null };

  const evPct = (modelProb * oddsValue * 100) - 100;

  return {
    evPctThrowInsAdvanced: Number(evPct.toFixed(2)),
    throwInsAdvancedLambda: Number(adjustedLambda.toFixed(2)),
    throwInsAdvancedProb: Number(modelProb.toFixed(4)),
  };
}
