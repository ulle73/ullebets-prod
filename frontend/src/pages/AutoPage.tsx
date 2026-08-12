import { BrainCircuit, ExternalLink, ShieldCheck } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { EntityLink } from '../components/EntityLink';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { PaginationBar } from '../components/PaginationBar';
import { StateNotice } from '../components/StateNotice';
import { WorkflowFilters, type WorkflowFilter } from '../components/WorkflowFilters';
import { useAuto } from '../data/queries';
import { autoQueryFromSearch, DEFAULT_PAGE_LIMIT, patchSearchParams } from '../data/workflow-query';
import { DIRECTION_OPTIONS, PERIOD_OPTIONS, SCOPE_OPTIONS, STAT_OPTIONS } from '../domain/workflow-filter-options';
import { formatExpectedRoi, formatOdds, formatProbability } from '../domain/formatters';

export function AutoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const readQuery = autoQueryFromSearch(searchParams);
  const query = useAuto(readQuery);
  const limit = readQuery.limit ?? DEFAULT_PAGE_LIMIT;
  const offset = readQuery.offset ?? 0;

  if (query.isLoading) return <StateNotice state="loading" title="Läser Auto" detail="Hämtar registrerade forward-val." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Auto kunde inte läsas" detail="Försök igen när datakällan är tillgänglig." />;

  const { summary, selections, page } = query.data;
  const filters: WorkflowFilter[] = [
    { key: 'stat', label: 'Stat', value: readQuery.stat ?? '', options: STAT_OPTIONS },
    { key: 'period', label: 'Period', value: readQuery.period ?? '', options: PERIOD_OPTIONS },
    { key: 'scope', label: 'Lag/scope', value: readQuery.scope ?? '', options: SCOPE_OPTIONS },
    { key: 'direction', label: 'Riktning', value: readQuery.direction ?? '', options: DIRECTION_OPTIONS },
  ];

  const changeFilter = (key: string, value: string) => setSearchParams(patchSearchParams(searchParams, { [key]: value }, { resetOffset: true }));
  const changeLimit = (value: number) => setSearchParams(patchSearchParams(searchParams, { limit: value }, { resetOffset: true }));
  const changePage = (value: number) => setSearchParams(patchSearchParams(searchParams, { offset: value }));

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Registrerade forward-val" title="Auto" subtitle="Här visas val som redan registrerats av systemets urvalspolicy. Sidan skapar inga egna kandidater." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Registrerade val" value={summary.total} detail="Matchar aktuellt filter" tone="brand" icon={<ShieldCheck size={14} />} />
        <MetricTile label="Giltiga forward" value={summary.valid} detail="Giltiga för forward-utvärdering" icon={<BrainCircuit size={14} />} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Ej forward-performance" tone="warn" />
      </div>
      <WorkflowFilters filters={filters} pageLimit={limit} onFilterChange={changeFilter} onPageLimitChange={changeLimit} />
      {selections.length === 0 ? <StateNotice state="empty" title="Inga registrerade forward-val" detail="Inga val matchar den aktuella läsvyn." /> : (
        <section className="product-section auto-list" aria-label="Forward-val">
          {selections.map((row, index) => {
            const matchLabel = `${row.homeTeamName ?? 'Okänt lag'} – ${row.awayTeamName ?? 'Okänt lag'}`;
            return (
              <article className="auto-row" key={row.selectionKey ?? `${row.matchKey ?? 'selection'}:${index}`}>
                <div>
                  <EntityLink kind="league" id={row.leagueKey} className="eyebrow">{row.leagueName ?? 'Liga saknas'}</EntityLink>
                  <h3>
                    <EntityLink kind="team" id={row.homeTeamKey}>{row.homeTeamName ?? 'Okänt lag'}</EntityLink>
                    <span aria-hidden="true"> – </span>
                    <EntityLink kind="team" id={row.awayTeamKey}>{row.awayTeamName ?? 'Okänt lag'}</EntityLink>
                  </h3>
                  <p>{[row.direction?.toUpperCase(), row.statKey, row.scope, row.period].filter(Boolean).join(' · ')}</p>
                  <EntityLink kind="match" id={row.matchKey} className="quiet-link" ariaLabel={`Öppna ${matchLabel}`}><ExternalLink size={13} aria-hidden="true" />Matchdetalj</EntityLink>
                </div>
                <div className="auto-row__metrics">
                  <span><small>Line</small><strong>{row.lineValue ?? '—'}</strong></span>
                  <span><small>Odds</small><strong>{formatOdds(row.selectedOdds)}</strong></span>
                  <span><small>Modell P</small><strong>{formatProbability(row.predictedWinProbability)}</strong></span>
                  <span><small>EV</small><strong>{formatExpectedRoi(row.expectedRoiUnits)}</strong></span>
                </div>
              </article>
            );
          })}
        </section>
      )}
      <PaginationBar offset={offset} limit={limit} total={summary.total} hasMore={page.hasMore} onPageChange={changePage} />
    </div>
  );
}
