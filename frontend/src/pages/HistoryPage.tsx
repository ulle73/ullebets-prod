import { Archive, ShieldAlert } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useResults } from '../data/queries';

export function HistoryPage() {
  const query = useResults();
  if (query.isLoading) return <StateNotice state="loading" title="Läser historik" detail="Historiken hämtas från V2 forward_results." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Historik kunde inte läsas" detail="Inga historiska frontend-snapshots används." />;

  const { summary } = query.data;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Persistenta resultat" title="Historik" subtitle="Historiken visar det som faktiskt finns i forward_results. Inga backtesttal eller ROI-värden ligger hårdkodade i frontend." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Rader" value={summary.rows} detail="forward_results" icon={<Archive size={14} />} />
        <MetricTile label="Giltigt avgjorda" value={summary.settled} detail={`${summary.wins} W · ${summary.losses} L`} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Ej performance" tone="warn" icon={<ShieldAlert size={14} />} />
      </div>
      {query.data.rows.length === 0 ? <StateNotice state="empty" title="Ingen historik ännu" detail="När V2 har forward_results visas de här automatiskt." /> : (
        <section className="evidence-lanes">
          <article><span className="evidence-lane__label">Settled</span><h2>{summary.settled}</h2><p>Rader som V2 markerar giltiga för performance.</p></article>
          <article><span className="evidence-lane__label evidence-lane__label--forward">Exkluderade</span><h2>{summary.excluded}</h2><p>Behålls för audit och blandas inte in i performance.</p></article>
        </section>
      )}
    </div>
  );
}
