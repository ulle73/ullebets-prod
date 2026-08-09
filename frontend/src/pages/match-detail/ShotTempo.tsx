import { Crown, Scale, TrendingUp } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import type { ShotTempoState as TempoView } from './view-model';

const ICONS: Record<string, ReactNode> = {
  leading: <Crown size={16} />,
  drawing: <Scale size={16} />,
  trailing: <TrendingUp size={16} />,
};

function number(value: number | null): string {
  return value === null ? '—' : value.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function percent(value: number | null): string {
  if (value === null) return '—';
  return `${value >= 0 ? '+' : ''}${Math.round(value)}%`;
}

function TempoBar({ label, view, tone }: { label: string; view: TempoView['home']; tone: 'home' | 'away' }) {
  const style = {
    '--tempo-value': `${(view.ratio ?? 0) * 100}%`,
    '--tempo-league': `${(view.leagueRatio ?? 0) * 100}%`,
  } as CSSProperties;
  return (
    <div className={`tempo-row tempo-row--${tone}`}>
      <span>{label}</span>
      <strong>{number(view.value)}</strong>
      <span className="tempo-bar" style={style} aria-hidden="true"><i />{view.leagueRatio !== null ? <b /> : null}</span>
      <em className={view.deltaPercent !== null && view.deltaPercent >= 0 ? 'is-positive' : 'is-negative'}>{percent(view.deltaPercent)}</em>
    </div>
  );
}

export function ShotTempo({ states, homeLabel, awayLabel }: { states: TempoView[]; homeLabel: string; awayLabel: string }) {
  return (
    <section className="analytics-panel tempo-panel">
      <header className="analytics-section-title"><h2>Skottempo efter matchläge</h2><span>Skott / min</span></header>
      <div className="tempo-grid">
        {states.map((state) => (
          <figure className="tempo-state" aria-label={`Skottempo ${state.label}`} key={state.key}>
            <figcaption>{ICONS[state.key]}<strong>{state.label}</strong></figcaption>
            <TempoBar label={homeLabel} view={state.home} tone="home" />
            <TempoBar label={awayLabel} view={state.away} tone="away" />
          </figure>
        ))}
      </div>
    </section>
  );
}
