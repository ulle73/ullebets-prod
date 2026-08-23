import { CircleSlash2, Target, TrendingUp, Trophy } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { ForwardResultTable } from '../components/ForwardResultTable';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { PaginationBar } from '../components/PaginationBar';
import { StateNotice } from '../components/StateNotice';
import { WorkflowFilters, type WorkflowFilter } from '../components/WorkflowFilters';
import { useResults } from '../data/queries';
import { DEFAULT_PAGE_LIMIT, patchSearchParams, resultsQueryFromSearch } from '../data/workflow-query';
import { CHECKPOINT_OPTIONS, DIRECTION_OPTIONS, PERIOD_OPTIONS, RESULT_STATUS_OPTIONS, SCOPE_OPTIONS, STAT_OPTIONS } from '../domain/workflow-filter-options';

function percentage(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${value > 0 ? '+' : ''}${value.toLocaleString('sv-SE', { maximumFractionDigits: 1 })} %`;
}

function units(value: number | undefined): string {
  if (value === undefined) return 'saknas';
  return `${value > 0 ? '+' : ''}${value.toLocaleString('sv-SE', { maximumFractionDigits: 2 })} u`;
}

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
    { key: 'checkpoint', label: 'Checkpoint', value: readQuery.checkpoint ?? '', options: CHECKPOINT_OPTIONS },
  ];

  const changeFilter = (key: string, value: string) => setSearchParams(patchSearchParams(searchParams, { [key]: value }, { resetOffset: true }));
  const changeLimit = (value: number) => setSearchParams(patchSearchParams(searchParams, { limit: value }, { resetOffset: true }));
  const changePage = (value: number) => setSearchParams(patchSearchParams(searchParams, { offset: value }));

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Forward-resultat" title="Resultatloop" subtitle="Settlement, exclusions och closing-information visas från registrerade resultat. Filtren körs i read-lagret och ändrar inte underliggande data." />
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Rättade spel" value={summary.settled} detail={`${summary.wins} vinst · ${summary.losses} förlust · ${summary.pushes} push`} tone="brand" icon={<Trophy size={14} />} />
        <MetricTile label="ROI" value={percentage(summary.roiPct)} detail={`${units(summary.pnlUnits)} på ${units(summary.stakeUnits)}`} tone={(summary.roiPct ?? 0) >= 0 ? 'good' : 'bad'} icon={<TrendingUp size={14} />} />
        <MetricTile label="CLV slagna" value={percentage(summary.clvBeatRatePct)} detail={`${summary.beatClosingLine ?? 0}/${summary.officialClvObservations ?? 0} officiella observationer`} tone="good" icon={<Target size={14} />} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Kvar för audit" tone="warn" icon={<CircleSlash2 size={14} />} />
      </div>
      <WorkflowFilters filters={filters} pageLimit={limit} onFilterChange={changeFilter} onPageLimitChange={changeLimit} />
      {rows.length === 0 ? <StateNotice state="empty" title="Inga forward-resultat" detail="Inga resultat matchar den aktuella läsvyn." /> : <ForwardResultTable rows={rows} />}
      <PaginationBar offset={offset} limit={limit} total={summary.groups ?? summary.rows} hasMore={page.hasMore} onPageChange={changePage} />
    </div>
  );
}
