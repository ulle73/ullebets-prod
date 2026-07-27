export function evPctFoulsAdvanced({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeBundle,
  awayBundle,
}) {
  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctFoulsAdvanced: null };

  const getMetric = (bundle, group, key) => {
    const profile = bundle?.home || bundle?.away;
    const val = profile?.statistics?.[group]?.[key]?.ALL?.value;
    return val ? parseFloat(val) : null;
  };

  const homeTackles = getMetric(homeBundle, "matchOverview", "totalTackle");
  const awayTackles = getMetric(awayBundle, "matchOverview", "totalTackle");
  
  // Note: duelWonPercent is a percentage, might need parsing if string "50%"
  // Assuming the reader handles it or it's a number. In engine.js readPeriodValue handles it.
  // But here we are reading raw value. Let's assume it's a number for now or simple parse.
  
  let adjustment = 1;

  // Aggression Logic: More tackles -> more fouls likely
  if (homeTackles !== null && awayTackles !== null) {
    const diff = homeTackles - awayTackles;
    adjustment += (diff * 0.02); 
  }

  const adjustedLambda = baseLambda * adjustment;
  const modelProb = probabilityOf(adjustedLambda);
  
  if (!modelProb) return { evPctFoulsAdvanced: null };

  const evPct = (modelProb * oddsValue * 100) - 100;

  return {
    evPctFoulsAdvanced: Number(evPct.toFixed(2)),
    foulsAdvancedLambda: Number(adjustedLambda.toFixed(2)),
    foulsAdvancedProb: Number(modelProb.toFixed(4)),
  };
}
