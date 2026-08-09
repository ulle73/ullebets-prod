import type { CSSProperties } from 'react';
import type { StatComparisonRow as StatView } from './view-model';

function formatValue(value: number | null): string {
  if (value === null) return '—';
  return new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 2 }).format(value);
}

function abbreviation(name: string | null, fallback: string): string {
  return name?.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 3).toLocaleUpperCase('sv-SE') || fallback;
}

function Delta({ delta, homeName, awayName }: { delta: StatView['forDelta']; homeName: string | null; awayName: string | null }) {
  if (delta.leader === 'missing' || delta.value === null) return <span className="stat-delta stat-delta--missing">—</span>;
  if (delta.leader === 'equal') return <span className="stat-delta stat-delta--equal">=</span>;
  const team = delta.leader === 'home' ? abbreviation(homeName, 'HEM') : abbreviation(awayName, 'BOR');
  return <span className={`stat-delta stat-delta--${delta.leader}`}>{team} +{formatValue(delta.value)}</span>;
}

function Rank({ value }: { value: number | null }) {
  return <span className="stat-rank">{value === null ? '—' : `#${value}`}</span>;
}

function Bar({ ratio, leagueRatio, direction, tone }: { ratio: number | null; leagueRatio: number | null; direction: 'home' | 'away'; tone: 'for' | 'against' }) {
  const style = {
    '--bar-value': `${(ratio ?? 0) * 100}%`,
    '--league-value': `${(leagueRatio ?? 0) * 100}%`,
  } as CSSProperties;
  return (
    <span className={`opposing-bar opposing-bar--${direction} opposing-bar--${tone}`} style={style} aria-hidden="true">
      <span className="opposing-bar__fill" />
      {leagueRatio !== null ? <span className="opposing-bar__league" /> : null}
    </span>
  );
}

function TeamWing({ team, direction }: { team: StatView['home']; direction: 'home' | 'away' }) {
  const values = (
    <span className="stat-wing__values">
      <span><strong>{formatValue(team.for.value)}</strong><Rank value={team.for.rank} /></span>
      <span><strong>{formatValue(team.against.value)}</strong><Rank value={team.against.rank} /></span>
    </span>
  );
  const bars = (
    <span className="stat-wing__bars">
      <Bar ratio={team.for.ratio} leagueRatio={team.for.leagueRatio} direction={direction} tone="for" />
      <Bar ratio={team.against.ratio} leagueRatio={team.against.leagueRatio} direction={direction} tone="against" />
    </span>
  );
  return <span className={`stat-wing stat-wing--${direction}`} role="cell">{direction === 'home' ? <>{bars}{values}</> : <>{values}{bars}</>}</span>;
}

export function StatComparison({ rows, homeName, awayName }: { rows: StatView[]; homeName: string | null; awayName: string | null }) {
  return (
    <section className="analytics-panel stat-comparison" role="table" aria-label="Lagstatistik för och emot">
      <header className="stat-comparison__legend" role="row">
        <strong>{homeName ?? 'Hemmalag'}</strong>
        <span className="stat-legend-items">
          <span><i className="legend-swatch legend-swatch--for" />För</span>
          <span><i className="legend-swatch legend-swatch--against" />Emot</span>
          <span><i className="legend-tick" />Ligasnitt</span>
          <span><i className="legend-rank">#</i>Rank</span>
        </span>
        <strong>{awayName ?? 'Bortalag'}</strong>
      </header>
      <div className="stat-comparison__body">
        {rows.map((row) => (
          <div className="stat-comparison__row" role="row" key={row.key}>
            <TeamWing team={row.home} direction="home" />
            <span className="stat-comparison__metric" role="rowheader">
              <strong>{row.label}</strong>
              <span><Delta delta={row.forDelta} homeName={homeName} awayName={awayName} /><Delta delta={row.againstDelta} homeName={homeName} awayName={awayName} /></span>
            </span>
            <TeamWing team={row.away} direction="away" />
          </div>
        ))}
      </div>
    </section>
  );
}
