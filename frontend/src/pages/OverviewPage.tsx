import { Activity, CalendarDays, CircleAlert, SlidersHorizontal } from 'lucide-react';
import { previewMatches, previewSignals } from '../data/preview-data';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';

export function OverviewPage() {
  const anchorMatch = previewMatches[0]!;
  const overSignals = previewSignals.filter((signal) => signal.direction === 'OVER');
  const underSignals = previewSignals.filter((signal) => signal.direction === 'UNDER');

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <p className="eyebrow">Workspace · Översikt</p>
          <h2>Bästa signaler</h2>
          <p className="page-subtitle">Snabbaste vägen från match till vad modellen faktiskt säger — med evidensstatus synlig.</p>
        </div>
        <div className="summary-strip" aria-label="Översiktsstatus">
          <span><CalendarDays size={14} />8 aug 2026</span>
          <span><Activity size={14} />{previewMatches.length} matcher</span>
          <span><CircleAlert size={14} />{previewSignals.filter((signal) => signal.evidence === 'excluded').length} exkluderade</span>
        </div>
      </section>

      <StateNotice state="excluded" title="Förhandsdata – inte spelrekommendationer" detail="Brasileirão-signalerna nedan visar V2/V6-fältens riktiga UI-kontrakt men ligger utanför V6:s träningsdomän och är därför ej spelbara." />

      <div className="filter-toolbar">
        <span><SlidersHorizontal size={15} aria-hidden="true" />Filter</span>
        <button type="button" className="filter-button is-active">Alla ligor</button>
        <button type="button" className="filter-button">Alla stats</button>
        <span className="filter-spacer" />
        <span className="freshness">Senaste checkpoint: T-2H</span>
      </div>

      <div className="signal-columns">
        <section className="signal-column">
          <header className="signal-column__header"><span className="signal-column__dot signal-column__dot--over" /><h3>Över</h3><span>{overSignals.length} signal</span></header>
          <div className="signal-list">{overSignals.map((signal) => <SignalCard key={signal.id} signal={signal} homeTeamName={anchorMatch.homeTeamName} awayTeamName={anchorMatch.awayTeamName} />)}</div>
        </section>
        <section className="signal-column">
          <header className="signal-column__header"><span className="signal-column__dot signal-column__dot--under" /><h3>Under</h3><span>{underSignals.length} signaler</span></header>
          <div className="signal-list">{underSignals.map((signal) => <SignalCard key={signal.id} signal={signal} homeTeamName={anchorMatch.homeTeamName} awayTeamName={anchorMatch.awayTeamName} />)}</div>
        </section>
      </div>
    </div>
  );
}
