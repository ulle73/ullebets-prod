// Optimized Universal Formulas (derived from run_simulator_all.js)
const OPTIMIZED_SETTINGS = {
  totalShotsOnGoal: {
    home: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.85, bias: 2 },
    away: { weights: { recent: 3, medium: 2, old: 1 }, multiplier: 0.8, bias: 1 }
  },
  shotsOnGoal: {
    home: { weights: { recent: 4, medium: 2, old: 1 }, multiplier: 0.85, bias: 1 },
    away: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.85, bias: -0.5 }
  },
  cornerKicks: {
    home: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 2 },
    away: { weights: { recent: 3, medium: 2, old: 1 }, multiplier: 0.8, bias: 0.5 }
  },
  throwIns: {
    home: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 2 },
    away: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 2 }
  },
  fouls: {
    home: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.9, bias: 0.5 },
    away: { weights: { recent: 3, medium: 2, old: 1 }, multiplier: 0.8, bias: 2 }
  },
  offsides: {
    home: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 1 },
    away: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 1 }
  },
  goalKicks: {
    home: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 2 },
    away: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 2 }
  },
  yellowCards: {
    home: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 1 },
    away: { weights: { recent: 2, medium: 1, old: 1 }, multiplier: 0.8, bias: 2 }
  }
};

/**
 * Universal Optimized Formula
 * Uses stat-specific optimized parameters derived from ALL teams
 */
export function evPctUniversalOptimized({
  baseResult,
  oddsValue,
  implied,
  probabilityOf,
  homeBundle,
  awayBundle,
  params, // Should contain: statKey, scope (e.g., "home", "away")
}) {
  if (!params || !params.statKey) {
    return { evPctUniversalOptimized: null };
  }

  const { statKey, scope } = params;
  
  // Determine if this is a home or away prediction
  const isHome = scope === "home" || scope === "homeTeam";
  const settings = OPTIMIZED_SETTINGS[statKey]?.[isHome ? "home" : "away"];

  if (!settings) {
    console.warn(`No optimized settings for statKey: ${statKey}`);
    return { evPctUniversalOptimized: null };
  }

  // Use the optimized multiplier and bias
  const { multiplier, bias } = settings;
  
  // Get base lambda from baseResult
  const baseLambda = baseResult?.lambda;
  if (!Number.isFinite(baseLambda)) {
    return { evPctUniversalOptimized: null };
  }

  // Apply the universal formula: Predicted = (WMA_Value * multiplier) + bias
  // Note: The WMA weighting is already baked into baseLambda calculation
  // Here we just apply the multiplier and bias adjustments
  const adjustedLambda = (baseLambda * multiplier) + bias;
  
  const modelProb = probabilityOf(adjustedLambda);
  if (!modelProb) {
    return { evPctUniversalOptimized: null };
  }

  const evPct = (modelProb * oddsValue * 100) - 100;

  return {
    evPctUniversalOptimized: Number(evPct.toFixed(4)),
    universalOptimizedLambda: Number(adjustedLambda.toFixed(2)),
    universalOptimizedProb: Number(modelProb.toFixed(4)),
  };
}
