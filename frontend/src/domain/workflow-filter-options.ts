import type { FilterOption } from '../components/WorkflowFilters';

export const STAT_OPTIONS: FilterOption[] = [
  { value: '', label: 'Alla stats' },
  { value: 'shotsOnGoal', label: 'Skott på mål' },
  { value: 'totalShots', label: 'Skott' },
  { value: 'cornerKicks', label: 'Hörnor' },
  { value: 'yellowCards', label: 'Gula kort' },
  { value: 'freeKicks', label: 'Frisparkar' },
  { value: 'fouls', label: 'Fouls' },
  { value: 'totalTackle', label: 'Tacklingar' },
  { value: 'offsides', label: 'Offsides' },
];

export const PERIOD_OPTIONS: FilterOption[] = [
  { value: '', label: 'Alla perioder' },
  { value: 'ALL', label: 'Hela matchen' },
  { value: '1ST', label: '1:a halvlek' },
  { value: '2ND', label: '2:a halvlek' },
];

export const SCOPE_OPTIONS: FilterOption[] = [
  { value: '', label: 'Alla scopes' },
  { value: 'home', label: 'Hemmalaget' },
  { value: 'away', label: 'Bortalaget' },
  { value: 'total', label: 'Totalt' },
];

export const DIRECTION_OPTIONS: FilterOption[] = [
  { value: '', label: 'Alla riktningar' },
  { value: 'over', label: 'OVER' },
  { value: 'under', label: 'UNDER' },
];

export const RESULT_STATUS_OPTIONS: FilterOption[] = [
  { value: '', label: 'Alla statusar' },
  { value: 'settled', label: 'Avgjorda' },
];
