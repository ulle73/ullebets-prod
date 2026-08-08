import { Database, GitBranch, ShieldCheck } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useModel } from '../data/queries';

export function ModelPage() {
  const query = useModel();
  if (query.isLoading) return <StateNotice state="loading" title="Läser modellstatus" detail="Hämtar modell- och forwardräknare från V2." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Modellstatus kunde inte läsas" detail="Frontend använder inga sparade proof-tal." />;

  const data = query.data;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="V2 live read" title="Modell & proof" subtitle="Modell-ID, policy-ID och evidensräknare kommer från persistenta V2-collections." />
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Model scores" value={data.scoreCount} detail="ev_model_scores" icon={<Database size={14} />} />
        <MetricTile label="Forward selections" value={data.forwardSelectionCount} detail="forward_bets" tone="brand" icon={<GitBranch size={14} />} />
        <MetricTile label="Settled forward" value={data.settledForwardCount} detail="valid_for_performance" />
        <MetricTile label="Official CLV" value={data.officialClvCount} detail="closing_quality=t10" tone="good" icon={<ShieldCheck size={14} />} />
      </div>
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Persistenta identiteter</p><h2>Modeller</h2></div></div>
        {data.modelIds.length ? <div className="league-chip-grid">{data.modelIds.map((id) => <span key={id}>{id}</span>)}</div> : <StateNotice state="empty" title="Inga model_id i ev_model_scores" detail="Ingen modellidentitet fylls i från frontend." />}
      </section>
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Registrerade urval</p><h2>Policy-ID</h2></div></div>
        {data.policyIds.length ? <div className="league-chip-grid">{data.policyIds.map((id) => <span key={id}>{id}</span>)}</div> : <StateNotice state="empty" title="Inga policy-ID i forward_bets" detail="Frontend gissar inte vilken policy som är aktiv." />}
      </section>
    </div>
  );
}
