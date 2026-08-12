import { Archive, ShieldAlert } from 'lucide-react';
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

export function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const readQuery = resultsQueryFromSearch(searchParams);
  const query = useResults(readQuery);
  const limit = readQuery.limit ?? DEFAULT_PAGE_LIMIT;
  const offset = readQuery.offset ?? 0;

  if (query.isLoading) return <StateNotice state="loading" title="Läser historik" detail="Hämtar persistenta forward-resultat." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Historik kunde inte läsas" detail="Ingen lokal eller hårdkodad historik används som ersättning." />;

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
      <PageHeader eyebrow="Persistenta resultat" title="Historik" subtitle="Historiken visar registrerade forward-resultat för granskning. Historiska utfall presenteras som historik och används inte som löfte om framtida avkastning." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Rader" value={summary.rows} detail="Persistenta resultat" icon={<Archive size={14} />} />
        <MetricTile label="Giltigt avgjorda" value={summary.settled} detail={`${summary.wins} W · ${summary.losses} L`} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Ej performance" tone="warn" icon={<ShieldAlert size={14} />} />
      </div>
      <WorkflowFilters filters={filters} pageLimit={limit} onFilterChange={changeFilter} onPageLimitChange={changeLimit} />
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Audit trail</p><h2>Historikrader</h2></div></div>
        {rows.length === 0 ? <StateNotice state="empty" title="Ingen historik ännu" detail="När registrerade forward-resultat finns visas de här automatiskt." /> : <ForwardResultTable rows={rows} ariaLabel="Historikrader" />}
      </section>
      <PaginationBar offset={offset} limit={limit} total={summary.rows} hasMore={page.hasMore} onPageChange={changePage} />
    </div>
  );
}
