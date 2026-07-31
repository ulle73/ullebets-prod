export function evPctGoalKicksAdvanced({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeBundle,
  awayBundle,
}) {
  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) return { evPctGoalKicksAdvanced: null };

  const getMetric = (bundle, group, key) => {
    const profile = bundle?.home || bundle?.away;
    const val = profile?.statistics?.[group]?.[key]?.ALL?.value;
    return val ? parseFloat(val) : null;
  };

  // Goal Kicks are caused by OPPONENT shots off target
  // So for Home Goal Kicks, we look at Away Shots Off Target
  
  const homeShotsOff = getMetric(homeBundle, "shots", "shotsOffGoal");
  const awayShotsOff = getMetric(awayBundle, "shots", "shotsOffGoal");
  
  const homePossession = getMetric(homeBundle, "matchOverview", "ballPossession");
  const awayPossession = getMetric(awayBundle, "matchOverview", "ballPossession");

  let adjustment = 1;

  // Logic: If Home is expected to concede many goal kicks, it means Away shoots off target a lot.
  // But here we are adjusting the lambda for the *selected team/match*.
  // If we are predicting Total Goal Kicks in the match:
  // More shots off target (combined) -> More goal kicks.
  
  if (homeShotsOff !== null && awayShotsOff !== null) {
    const totalShotsOff = homeShotsOff + awayShotsOff;
    // Compare to some baseline? Or just use the difference between teams to skew?
    // Let's use the sum to boost if high.
    if (totalShotsOff > 10) adjustment += 0.1;
    if (totalShotsOff < 6) adjustment -= 0.1;
  }

  // Possession Logic: High possession usually means fewer goal kicks conceded, but maybe more forced?
  // Actually, low possession -> defending deep -> clearing/conceding goal kicks?
  // Let's stick to shots off target as primary driver.
  
  const adjustedLambda = baseLambda * adjustment;
  const modelProb = probabilityOf(adjustedLambda);
  
  if (!modelProb) return { evPctGoalKicksAdvanced: null };

  const evPct = (modelProb * oddsValue * 100) - 100;

  return {
    evPctGoalKicksAdvanced: Number(evPct.toFixed(2)),
    goalKicksAdvancedLambda: Number(adjustedLambda.toFixed(2)),
    goalKicksAdvancedProb: Number(modelProb.toFixed(4)),
  };
}
