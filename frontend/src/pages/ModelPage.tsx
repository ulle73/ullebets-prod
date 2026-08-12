import { Activity, GitBranch, ShieldCheck } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useModel } from '../data/queries';

interface RuntimeModelStates {
  modelStatuses?: string[];
  policyStatuses?: string[];
}

function humanizeStatus(value: string): string {
  const normalized = value.trim().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').toLocaleLowerCase('sv-SE');
  return normalized ? `${normalized[0]?.toLocaleUpperCase('sv-SE') ?? ''}${normalized.slice(1)}` : 'Okänd status';
}

export function ModelPage() {
  const query = useModel();
  if (query.isLoading) return <StateNotice state="loading" title="Läser modellstatus" detail="Hämtar registrerade modell-, policy- och evidensvärden." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Modellstatus kunde inte läsas" detail="Frontend använder inga sparade proof-tal som ersättning." />;

  const data = query.data;
  const runtime = data as typeof data & RuntimeModelStates;
  const modelStatuses = runtime.modelStatuses ?? [];
  const policyStatuses = runtime.policyStatuses ?? [];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Modell & evidens"
        title="Modell & proof"
        subtitle="Visar registrerade modell- och policystatusar samt evidensvolym. Antal observationer är inte proof på positiv forward-ROI eller CLV."
      />
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Modellscorer" value={data.scoreCount} detail="Registrerade scorer" icon={<Activity size={14} />} />
        <MetricTile label="Forward-val" value={data.forwardSelectionCount} detail="Registrerade observationer" tone="brand" icon={<GitBranch size={14} />} />
        <MetricTile label="Avgjorda forward" value={data.settledForwardCount} detail="Giltiga för utvärdering" />
        <MetricTile label="Officiell closing" value={data.officialClvCount} detail="T-10-mätningar" tone="good" icon={<ShieldCheck size={14} />} />
      </div>

      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Persisted runtime state</p><h2>Evidensläge</h2></div></div>
        <p className="proof-caveat">Antal observationer är inte proof. Positiv forward-ROI eller CLV måste verifieras separat innan det får behandlas som evidens för framtida beslut.</p>
        <div className="evidence-lanes">
          <article>
            <span className="evidence-lane__label">Modellstatus</span>
            {modelStatuses.length ? <div className="league-chip-grid">{modelStatuses.map((status) => <span className="status-badge status-badge--unproven" key={status}>{humanizeStatus(status)}</span>)}</div> : <p>Ingen registrerad modellstatus finns i läsvyn.</p>}
          </article>
          <article>
            <span className="evidence-lane__label evidence-lane__label--forward">Policystatus</span>
            {policyStatuses.length ? <div className="league-chip-grid">{policyStatuses.map((status) => <span className="status-badge status-badge--partial" key={status}>{humanizeStatus(status)}</span>)}</div> : <p>Ingen registrerad policystatus finns i läsvyn.</p>}
          </article>
        </div>
      </section>

      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Registrerade identiteter</p><h2>Modeller</h2></div></div>
        {data.modelIds.length ? <div className="league-chip-grid">{data.modelIds.map((id) => <span key={id}>{id}</span>)}</div> : <StateNotice state="empty" title="Inga modell-ID registrerade" detail="Frontend fyller inte i en modellidentitet som saknas." />}
      </section>
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Registrerade urval</p><h2>Policy-ID</h2></div></div>
        {data.policyIds.length ? <div className="league-chip-grid">{data.policyIds.map((id) => <span key={id}>{id}</span>)}</div> : <StateNotice state="empty" title="Inga policy-ID registrerade" detail="Frontend gissar inte vilken policy som är aktiv." />}
      </section>
    </div>
  );
}
