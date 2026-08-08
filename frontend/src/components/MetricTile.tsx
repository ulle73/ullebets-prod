import type { ReactNode } from 'react';

export function MetricTile({ label, value, detail, tone = 'neutral', icon }: { label: string; value: ReactNode; detail?: string; tone?: 'neutral' | 'brand' | 'good' | 'warn' | 'bad'; icon?: ReactNode }) {
  return (
    <article className={`metric-tile metric-tile--${tone}`}>
      <div className="metric-tile__label">{icon}{label}</div>
      <strong className="metric-tile__value">{value}</strong>
      {detail ? <p>{detail}</p> : null}
    </article>
  );
}
