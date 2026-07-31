export function evPctShotsAdvanced({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeBundle,
  awayBundle,
}) {
  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctShotsAdvanced: null };

  // Helper to safely extract a metric from teamprofile statistics  
  const getMetric = (bundle, statKey) => {
    // bundle = { home: {...}, away: {...} } from fetchTeamProfilesBundle
    // We want home team's home profile stats
    const profile = bundle?.home || bundle?.away;
    const val = profile?.statistics?.[statKey]?.ALL?.value;
    return val ? parseFloat(val) : null;
  };

  // Use stats available in teamprofile: total Shots, totalTackle, etc.
  const homeShots = getMetric(homeBundle, "totalShotsOnGoal");
  const awayShots = getMetric(awayBundle, "totalShotsOnGoal");
  
  const homeTackles = getMetric(homeBundle, "totalTackle");
  const awayTackles = getMetric(awayBundle, "totalTackle");

  let adjustment = 1;

  // Shot volume logic: More shots historically -> expect more shots  
  if (homeShots && awayShots) {
    const diff = homeShots - awayShots; 
    adjustment += (diff * 0.01); // +1% per shot difference
  }

  // Defensive pressure logic: More tackles -> more possession regains -> more shots
  if (homeTackles && awayTackles) {
    const diff = homeTackles - awayTackles;
    adjustment += (diff * 0.005); 
  }

  const adjustedLambda = baseLambda * adjustment;
  const modelProb = probabilityOf(adjustedLambda);
  
  if (!modelProb) return { evPctShotsAdvanced: null };

  const evPct = (modelProb * oddsValue * 100) - 100;

  return {
    evPctShotsAdvanced: Number(evPct.toFixed(2)),
    shotsAdvancedLambda: Number(adjustedLambda.toFixed(2)),
    shotsAdvancedProb: Number(modelProb.toFixed(4)),
  };
}
