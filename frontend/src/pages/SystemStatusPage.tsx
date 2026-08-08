import { Database, RadioTower, ShieldCheck } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { StatusBadge } from '../components/StatusBadge';
import { systemEvidenceSnapshot } from '../data/product-snapshots';

export function SystemStatusPage() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Data & operations" title="Systemstatus" subtitle="Detta är en tidsstämplad verifieringssnapshot, inte en live-status som frontend låtsas uppdatera." aside={<span className="source-chip">{systemEvidenceSnapshot.label}</span>} />
      <div className="checkpoint-status-grid">
        {systemEvidenceSnapshot.checkpointRows.map((checkpoint) => (
          <article className="checkpoint-status-card" key={checkpoint.label}>
            <div><span>{checkpoint.label}</span><StatusBadge status={checkpoint.status} /></div>
            <strong>{checkpoint.rows ?? '—'}</strong>
            <small>{checkpoint.matches === null ? 'Ingen accepterad live-evidens' : `${checkpoint.matches} matcher`}</small>
          </article>
        ))}
      </div>
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Closing lines" value={systemEvidenceSnapshot.closingLines} detail="I sparad snapshot" tone="warn" icon={<Database size={14} />} />
        <MetricTile label="Official CLV" value={systemEvidenceSnapshot.clvState} detail="T-10 krävs" tone="warn" icon={<ShieldCheck size={14} />} />
        <MetricTile label="Capture → V6" value={systemEvidenceSnapshot.v6CaptureScoring} detail="Hosted write-mode due window återstår" tone="brand" icon={<RadioTower size={14} />} />
      </div>
      <StateNotice state="excluded" title="T-30/T-10 och official CLV är UNPROVEN i denna snapshot" detail="Frontend visar inte äldre T-2H/T-1D-priser som closing och räknar inte missing closing som 0 % CLV." />
    </div>
  );
}
