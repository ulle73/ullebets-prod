import { CircleSlash2, CircleX, Trophy } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { ForwardResultTable } from '../components/ForwardResultTable';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { PaginationBar } from '../components/PaginationBar';
import { StateNotice } from '../components/StateNotice';
import { WorkflowFilters, type WorkflowFilter } from '../components/WorkflowFilters';
import { useResults } from '../data/queries';
import { DEFAULT_PAGE_LIMIT, patchSearchParams, resultsQueryFromSearch } from '../data/workflow-query';
import { DIRECTION_OPTIONS, PERIOD_OPTIONS, RESULT_STATUS_OPTIONS, SCOPE_OPTIONS, STAT_OPTIONS } from '../domain/workflow-filter-options';

export function ResultsLoopPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const readQuery = resultsQueryFromSearch(searchParams);
  const query = useResults(readQuery);
  const limit = readQuery.limit ?? DEFAULT_PAGE_LIMIT;
  const offset = readQuery.offset ?? 0;

  if (query.isLoading) return <StateNotice state="loading" title="Läser resultatloop" detail="Hämtar registrerade forward-resultat." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Resultatloop kunde inte läsas" detail="Försök igen när datakällan är tillgänglig." />;

  const { summary, rows, page } = query.data;
  const filters: WorkflowFilter[] = [
    { key: 'status', label: 'Status', value: readQuery.status ?? '', options: RESULT_STATUS_OPTIONS },
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
      <PageHeader eyebrow="Forward-resultat" title="Resultatloop" subtitle="Settlement, exclusions och closing-information visas från registrerade resultat. Filtren körs i read-lagret och ändrar inte underliggande data." />
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Giltigt avgjorda" value={summary.settled} detail={`${summary.pushes} push`} tone="brand" />
        <MetricTile label="Vinster" value={summary.wins} detail="Settled" tone="good" icon={<Trophy size={14} />} />
        <MetricTile label="Förluster" value={summary.losses} detail="Settled" tone="bad" icon={<CircleX size={14} />} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Kvar för audit" tone="warn" icon={<CircleSlash2 size={14} />} />
      </div>
      <WorkflowFilters filters={filters} pageLimit={limit} onFilterChange={changeFilter} onPageLimitChange={changeLimit} />
      {rows.length === 0 ? <StateNotice state="empty" title="Inga forward-resultat" detail="Inga resultat matchar den aktuella läsvyn." /> : <ForwardResultTable rows={rows} />}
      <PaginationBar offset={offset} limit={limit} total={summary.rows} hasMore={page.hasMore} onPageChange={changePage} />
    </div>
  );
}
