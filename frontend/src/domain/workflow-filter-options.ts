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

export const CHECKPOINT_OPTIONS: FilterOption[] = [
  { value: '', label: 'Alla checkpoints' },
  { value: 'T_MINUS_3D', label: 'T-3 dagar' },
  { value: 'T_MINUS_2D', label: 'T-2 dagar' },
  { value: 'T_MINUS_1D', label: 'T-1 dag' },
  { value: 'T_MINUS_12H', label: 'T-12 timmar' },
  { value: 'T_MINUS_2H', label: 'T-2 timmar' },
  { value: 'T_MINUS_30M', label: 'T-30 minuter' },
  { value: 'T_MINUS_10M', label: 'T-10 minuter' },
];

export const RESULT_STATUS_OPTIONS: FilterOption[] = [
  { value: '', label: 'Alla statusar' },
  { value: 'settled', label: 'Avgjorda' },
];
