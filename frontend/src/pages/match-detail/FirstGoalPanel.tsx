import type { CSSProperties } from 'react';
import type { FirstGoalView } from './view-model';

function percentage(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toLocaleString('sv-SE', { maximumFractionDigits: 1 })}%`;
}

function Ring({ label, value, rank, tone }: { label: string; value: number | null; rank: number | null; tone: 'for' | 'against' }) {
  const style = { '--ring-value': `${Math.min(Math.max(value ?? 0, 0), 1) * 360}deg` } as CSSProperties;
  return (
    <div className={`first-goal-ring first-goal-ring--${tone}`}>
      <span>{label}</span>
      <div className="first-goal-ring__visual" style={style}><strong>{percentage(value)}</strong></div>
      <small>{rank === null ? '—' : `#${rank}`}</small>
    </div>
  );
}

function cluster(markers: FirstGoalView['markers']) {
  const groups = new Map<number, FirstGoalView['markers']>();
  for (const marker of markers) {
    if (marker.minute === null) continue;
    groups.set(marker.minute, [...(groups.get(marker.minute) ?? []), marker]);
  }
  return [...groups.entries()].sort(([left], [right]) => left - right);
}

function markerLabel(marker: FirstGoalView['markers'][number], homeName: string, awayName: string): string {
  const team = marker.side === 'home' ? homeName : awayName;
  return `${team} ${marker.event === 'scored' ? 'gör först' : 'släpper in först'}`;
}

export function FirstGoalPanel({ view, homeName, awayName }: { view: FirstGoalView; homeName: string; awayName: string }) {
  return (
    <section className="analytics-panel first-goal-panel">
      <header className="analytics-section-title"><h2>Första målet</h2></header>
      <div className="first-goal-layout">
        <div className="first-goal-share">
          <div className="first-goal-team"><strong>{homeName}</strong><div><Ring label="Gör först" value={view.home.scoreFirstPercentage} rank={view.home.scoreFirstRank} tone="for" /><Ring label="Släpper in först" value={view.home.concedeFirstPercentage} rank={view.home.concedeFirstRank} tone="against" /></div></div>
          <div className="first-goal-team first-goal-team--away"><strong>{awayName}</strong><div><Ring label="Gör först" value={view.away.scoreFirstPercentage} rank={view.away.scoreFirstRank} tone="for" /><Ring label="Släpper in först" value={view.away.concedeFirstPercentage} rank={view.away.concedeFirstRank} tone="against" /></div></div>
        </div>
        <div className="first-goal-timeline" role="img" aria-label="Första mål på tidsaxel 0 till 45 minuter">
          <div className="first-goal-timeline__axis">
            {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45].map((minute) => <span style={{ left: `${(minute / 45) * 100}%` }} key={minute}><i />{minute}</span>)}
            {cluster(view.markers).map(([minute, markers]) => (
              <div className="first-goal-cluster" style={{ left: `${(minute / 45) * 100}%` }} key={minute}>
                <strong>{minute.toLocaleString('sv-SE', { maximumFractionDigits: 1 })}'</strong>
                <span className="first-goal-cluster__dots">
                  {markers.map((marker) => <i className={`first-goal-marker first-goal-marker--${marker.side}-${marker.event}`} aria-label={markerLabel(marker, homeName, awayName)} key={marker.key} />)}
                </span>
              </div>
            ))}
          </div>
          <div className="first-goal-key">
            {view.markers.map((marker) => <span className={`first-goal-key__${marker.side}-${marker.event}`} key={marker.key}>{markerLabel(marker, homeName, awayName)}</span>)}
          </div>
        </div>
      </div>
    </section>
  );
}
