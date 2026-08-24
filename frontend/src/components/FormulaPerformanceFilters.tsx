import type { FormulaPerformanceQuery } from '../data/api';
import type { FormulaPerformanceFacet, FormulaPerformanceResponse } from '../domain/types';
import type { ReactNode } from 'react';


type Facets = FormulaPerformanceResponse['facets'];

const STAT_LABELS: Record<string, string> = {
  cornerKicks: 'Hörnor',
  shotsOnGoal: 'Skott på mål',
  totalShots: 'Skott',
  yellowCards: 'Gula kort',
  freeKicks: 'Frisparkar',
  fouls: 'Fouls',
  totalTackle: 'Tacklingar',
  offsides: 'Offsides',
};
const SCOPE_LABELS: Record<string, string> = { home: 'Hemmalaget', away: 'Bortalaget', total: 'Totalt' };
const PERIOD_LABELS: Record<string, string> = { ALL: 'Hela matchen', '1ST': '1:a halvlek', '2ND': '2:a halvlek' };
const DIRECTION_LABELS: Record<string, string> = { over: 'Över', under: 'Under' };

interface Props {
  query: FormulaPerformanceQuery;
  facets: Facets;
  onChange: (key: keyof FormulaPerformanceQuery, value: string) => void;
}

function options(facets: FormulaPerformanceFacet[], label: (facet: FormulaPerformanceFacet) => string = (facet) => facet.label) {
  return facets.map((facet) => (
    <option value={facet.value} key={facet.value}>{label(facet)} ({facet.count})</option>
  ));
}

function FilterSelect({ label, value, onChange, children }: { label: string; value: string | undefined; onChange: (value: string) => void; children: ReactNode }) {
  return (
    <label className="formula-filter">
      <span>{label}</span>
      <select aria-label={label} value={value ?? ''} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

export function FormulaPerformanceFilters({ query, facets, onChange }: Props) {
  return (
    <section className="formula-filter-panel" aria-label="Filtrera modelljämförelsen">
      <div className="formula-filter-panel__main">
        <FilterSelect label="Formel" value={query.formula} onChange={(value) => onChange('formula', value)}>
          <option value="">Alla formler</option>
          {options(facets.formulas)}
        </FilterSelect>
        <FilterSelect label="Statistik" value={query.stat} onChange={(value) => onChange('stat', value)}>
          <option value="">Alla statkeys</option>
          {options(facets.stats, (facet) => STAT_LABELS[facet.value] ?? facet.label)}
        </FilterSelect>
        <FilterSelect label="Scope" value={query.scope} onChange={(value) => onChange('scope', value)}>
          <option value="">Alla scopes</option>
          {options(facets.scopes, (facet) => SCOPE_LABELS[facet.value] ?? facet.label)}
        </FilterSelect>
        <FilterSelect label="Period" value={query.period} onChange={(value) => onChange('period', value)}>
          <option value="">Alla perioder</option>
          {options(facets.periods, (facet) => PERIOD_LABELS[facet.value] ?? facet.label)}
        </FilterSelect>
        <FilterSelect label="Checkpoint" value={query.checkpoint} onChange={(value) => onChange('checkpoint', value)}>
          <option value="">Alla tidpunkter</option>
          {options(facets.checkpoints, (facet) => facet.label.replace('T_MINUS_', 'T−'))}
        </FilterSelect>
      </div>
      <div className="formula-filter-panel__view" role="group" aria-label="Datavy">
        <button type="button" className={query.mode !== 'all_scores' ? 'is-active' : ''} aria-pressed={query.mode !== 'all_scores'} onClick={() => onChange('mode', 'positive_ev')}>Virtuella +EV-spel</button>
        <button type="button" className={query.mode === 'all_scores' ? 'is-active' : ''} aria-pressed={query.mode === 'all_scores'} onClick={() => onChange('mode', 'all_scores')}>Alla scorer</button>
      </div>
      <details className="formula-filter-panel__more">
        <summary>Fler filter</summary>
        <div>
          <FilterSelect label="Formelfamilj" value={query.family} onChange={(value) => onChange('family', value)}>
            <option value="">Alla familjer</option>
            {options(facets.families)}
          </FilterSelect>
          <FilterSelect label="Riktning" value={query.direction} onChange={(value) => onChange('direction', value)}>
            <option value="">Båda riktningar</option>
            {options(facets.directions, (facet) => DIRECTION_LABELS[facet.value] ?? facet.label)}
          </FilterSelect>
          <FilterSelect label="Liga" value={query.league} onChange={(value) => onChange('league', value)}>
            <option value="">Alla ligor</option>
            {options(facets.leagues)}
          </FilterSelect>
          <FilterSelect label="Status" value={query.status} onChange={(value) => onChange('status', value)}>
            <option value="">Alla statusar</option>
            <option value="open">Öppna</option>
            <option value="settled">Rättade</option>
            <option value="won">Vunna</option>
            <option value="lost">Förlorade</option>
            <option value="push">Push</option>
            <option value="excluded">Exkluderade</option>
          </FilterSelect>
        </div>
      </details>
    </section>
  );
}
