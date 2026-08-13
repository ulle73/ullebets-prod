export type StatKey = 'shotsOnGoal' | 'totalShots' | 'cornerKicks' | 'yellowCards' | 'freeKicks' | 'fouls' | 'totalTackle' | 'offsides';
export type PeriodKey = 'ALL' | '1ST' | '2ND';
export type ScopeKey = 'home' | 'away' | 'total';
export type ClosingQuality = 't10' | 't30_fallback' | null;

const statLabels: Record<StatKey, string> = {
  shotsOnGoal: 'Skott på mål',
  totalShots: 'Skott',
  cornerKicks: 'Hörnor',
  yellowCards: 'Gula kort',
  freeKicks: 'Frisparkar',
  fouls: 'Fouls',
  totalTackle: 'Tacklingar',
  offsides: 'Offsides',
};

const periodLabels: Record<PeriodKey, string> = {
  ALL: 'Match',
  '1ST': '1:a halvlek',
  '2ND': '2:a halvlek',
};

const scopeLabels: Record<ScopeKey, string> = {
  home: 'Hemmalaget',
  away: 'Bortalaget',
  total: 'Totalt',
};

function decimalPercent(value: number): string {
  return (value * 100).toLocaleString('sv-SE', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

export function formatProbability(value: number | null): string {
  return value === null ? 'Saknas' : `${decimalPercent(value)} %`;
}

export function formatExpectedRoi(value: number | null): string {
  if (value === null) return 'EV saknas';
  const formatted = decimalPercent(value);
  return `${value > 0 ? '+' : ''}${formatted} %`;
}

export function formatClv(value: number | null): string {
  if (value === null) return 'CLV saknas';
  // V2 stores clv_pct in percentage points, unlike model probabilities and EV.
  const formatted = value.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${value > 0 ? '+' : ''}${formatted} %`;
}

export function formatClosingQuality(value: ClosingQuality): string {
  if (value === 't10') return 'Officiell T-10';
  if (value === 't30_fallback') return 'T-30 fallback';
  return 'Closing saknas';
}

export function formatStat(value: StatKey): string {
  return statLabels[value];
}

export function formatPeriod(value: PeriodKey): string {
  return periodLabels[value];
}

export function formatScope(value: ScopeKey): string {
  return scopeLabels[value];
}

export function formatOdds(value: number | null): string {
  return value === null ? 'Odds saknas' : value.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatKickoff(iso: string): string {
  return new Intl.DateTimeFormat('sv-SE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Stockholm' }).format(new Date(iso));
}
