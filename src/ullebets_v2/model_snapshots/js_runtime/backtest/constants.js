export const STAT_PATTERNS = {
  totalShots: {
    keys: ["totalshots", "totalshotsongoal"],
    names: ["total shots"],
    rankKey: "totalShotsOnGoal",
  },
  shotsOnGoal: {
    keys: ["shotsongoal"],
    names: ["shots on goal", "shots on target"],
    rankKey: "shotsOnGoal",
  },
  cornerKicks: {
    keys: ["cornerkicks"],
    names: ["corner kicks", "corners"],
    rankKey: "cornerKicks",
  },
  yellowCards: {
    keys: ["yellowcards"],
    names: ["yellow cards"],
    rankKey: "yellowCards",
  },
  throwIns: {
    keys: ["throwins"],
    names: ["throw-ins"],
    rankKey: "throwIns",
  },
  freeKicks: {
    keys: ["freekicks"],
    names: ["free kicks"],
    rankKey: "freeKicks",
  },
  fouls: { keys: ["fouls"], names: ["fouls"], rankKey: "fouls" },
  totalTackle: {
    keys: ["totaltackle", "tackles"],
    names: ["tackles", "total tackles"],
    rankKey: "totalTackle",
  },
  offsides: { keys: ["offsides"], names: ["offsides"], rankKey: "offsides" },
};

export const PERIODS = ["ALL", "1ST", "2ND"];

export const DEFAULT_FORM = "all";
