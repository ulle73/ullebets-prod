import { BadgeCheck, FlaskConical, LockKeyhole } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { StatusBadge } from '../components/StatusBadge';
import { modelEvidenceSnapshot } from '../data/product-snapshots';

export function ModelPage() {
  const snapshot = modelEvidenceSnapshot;
  return (
    <div className="page-stack">
      <PageHeader eyebrow={`${snapshot.model} · ${snapshot.forwardPolicy}`} title="Modell & proof" subtitle="Sidan separerar historisk modellselektion från untouched forward evidence. Historisk ROI marknadsförs aldrig som framtida edge." aside={<StatusBadge status={snapshot.forward.status} />} />
      <section className="model-evidence-grid">
        <article className="model-evidence-card model-evidence-card--historical">
          <div className="model-evidence-card__icon"><FlaskConical size={18} /></div>
          <span className="evidence-lane__label">Historisk backtest</span>
          <strong className="hero-number">+28,65 %</strong>
          <p>{snapshot.historical.bets} bets · {snapshot.historical.matches} matcher · +{snapshot.historical.pnlUnits.toLocaleString('sv-SE', { minimumFractionDigits: 2 })} units</p>
          <small>Match-clustrat 95 %-intervall: +{snapshot.historical.intervalLowPct.toLocaleString('sv-SE')} % till +{snapshot.historical.intervalHighPct.toLocaleString('sv-SE')} %.</small>
        </article>
        <article className="model-evidence-card model-evidence-card--forward">
          <div className="model-evidence-card__icon"><LockKeyhole size={18} /></div>
          <span className="evidence-lane__label evidence-lane__label--forward">Untouched forward</span>
          <strong className="hero-number">0 in-domain</strong>
          <p>scores / selections / settlements / ROI / CLV i den sparade V6-auditen.</p>
          <StatusBadge status={snapshot.forward.status} />
        </article>
      </section>
      <StateNotice state="excluded" title="Promotion är BLOCKED — inte misslyckad" detail="Nästa giltiga modellbevis kräver framtida matcher från V6:s träningsdomän. Mer filtrering av samma historik skulle vara data mining." />
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Training domain</p><h2>Stödda ligor</h2></div><BadgeCheck size={17} className="brand-icon" /></div>
        <div className="league-chip-grid">{snapshot.supportedLeagues.map((league) => <span key={league}>{league}</span>)}</div>
      </section>
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Forward selections" value={snapshot.forward.selections} detail="In-domain" />
        <MetricTile label="Settlements" value={snapshot.forward.settlements} detail="Untouched V6" />
        <MetricTile label="CLV-rader" value={snapshot.forward.clvRows} detail="Official closing" />
      </div>
    </div>
  );
}
