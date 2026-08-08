import { Ban, BrainCircuit, ShieldCheck } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';
import { StatusBadge } from '../components/StatusBadge';
import { autoEvidenceSnapshot } from '../data/product-snapshots';
import { previewMatches, previewSignals } from '../data/preview-data';

export function AutoPage() {
  const match = previewMatches[0]!;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="V6 · registrerad policy" title="Auto" subtitle="Endast persistenta, in-domain forward-test-val får hamna i den spelbara listan." aside={<StatusBadge status={autoEvidenceSnapshot.status} />} />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Spelbara nu" value={`${autoEvidenceSnapshot.actionableSelections} spelbara V6-val`} detail="Sparad evidenssnapshot" tone="brand" icon={<ShieldCheck size={14} />} />
        <MetricTile label="In-domain scores" value={autoEvidenceSnapshot.inDomainScores} detail="Krävs före selection" icon={<BrainCircuit size={14} />} />
        <MetricTile label="OOD-diagnostik" value={autoEvidenceSnapshot.outOfDomainScores} detail="Får inte rankas som spel" tone="warn" icon={<Ban size={14} />} />
      </div>
      <StateNotice state="empty" title="Inga registrerade Forward-test-val i den sparade snapshoten" detail="Auto fylls först när V6 skapar en in-domain selection som redan passerat backendens registrerade policy. Frontend räknar inte ut eligibility själv." />
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Diagnostik</p><h2>Exkluderade Brazil-rader</h2></div><span className="muted-label">Utanför träningsdomän</span></div>
        <div className="detail-signal-grid">{previewSignals.map((signal) => <SignalCard key={signal.id} signal={signal} homeTeamName={match.homeTeamName} awayTeamName={match.awayTeamName} />)}</div>
      </section>
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Träningsdomän</p><h2>V6-stödda ligor</h2></div></div>
        <div className="league-chip-grid">{autoEvidenceSnapshot.supportedLeagues.map((league) => <span key={league}>{league}</span>)}</div>
      </section>
    </div>
  );
}
