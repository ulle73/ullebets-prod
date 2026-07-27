const DEFAULT_DISPLAY_ORDER = ["base", "leagueAvg"];

const INLINE_CONFIG = {
  cornerKicks: {
    display: ["leagueAvg", "multifactor"],
    blendWeight: 0.9,
    multifactor: {
      leagueWeight: 0.9,
    },
  },
  totalShots: {
    display: ["base", "leagueAvg"],
    blendWeight: 0.8,
  },
  yellowCards: {
    display: ["base", "multifactor"],
    blendWeight: 0.1,
    multifactor: {
      leagueWeight: 0.1,
    },
  },
};

const DEFAULT_CONFIG = {
  display: DEFAULT_DISPLAY_ORDER,
};

export function getFormulaConfig(statKey) {
  return INLINE_CONFIG[statKey] || DEFAULT_CONFIG;
}
