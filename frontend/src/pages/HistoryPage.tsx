import { Archive, ShieldAlert } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { operationalResultsSnapshot } from '../data/product-snapshots';

export function HistoryPage() {
  const diagnostic = operationalResultsSnapshot.diagnosticEvShadow;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Evidensfamiljer" title="Historik" subtitle="Historik visar exakt vilken evidensfamilj en siffra tillhör. Deskriptiva Brazil-rader blandas aldrig med V6-forward-proof." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Operational settled" value={operationalResultsSnapshot.settled} detail={`${operationalResultsSnapshot.wins} W · ${operationalResultsSnapshot.losses} L`} icon={<Archive size={14} />} />
        <MetricTile label="OOD-diagnostik" value={`${diagnostic.pnlUnits.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} u`} detail={`${diagnostic.rows} timing-valid EV-shadow-rader`} tone="warn" icon={<ShieldAlert size={14} />} />
        <MetricTile label="Deskriptiv ROI" value={`${diagnostic.roiPct.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`} detail="Brasilien · inte V6-forward-proof" tone="bad" />
      </div>
      <StateNotice state="excluded" title="OOD-diagnostik — inte V6-forward-proof" detail="De fem timing-giltiga EV-shadow-raderna slutade 2–3, -1,17 units och -23,40 % deskriptiv ROI. Brasilien ligger utanför den frysta V6-träningsdomänen." />
      <section className="product-section evidence-lanes">
        <article><span className="evidence-lane__label">Historisk / deskriptiv</span><h2>Inspektera utan att marknadsföra</h2><p>Backtest och OOD-operational data får användas för analys, men är inte untouched forward evidence.</p></article>
        <article><span className="evidence-lane__label evidence-lane__label--forward">Forward</span><h2>Väntar på in-domain settlement</h2><p>ROI och CLV för V6 visas först när tillräcklig faktisk forward-evidens finns.</p></article>
      </section>
    </div>
  );
}
