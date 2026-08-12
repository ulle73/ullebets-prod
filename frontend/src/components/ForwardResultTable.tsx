import { ExternalLink } from 'lucide-react';
import { EntityLink } from './EntityLink';
import type { ForwardResult } from '../domain/types';
import { formatOdds } from '../domain/formatters';

function units(value: number | null): string {
  if (value === null) return '—';
  return `${value > 0 ? '+' : ''}${value.toLocaleString('sv-SE', { maximumFractionDigits: 2 })} u`;
}

function officialClv(row: ForwardResult): string {
  if (!row.officialClv || row.clvPct === null) return 'CLV saknas';
  const value = `${row.clvPct > 0 ? '+' : ''}${row.clvPct.toLocaleString('sv-SE', { maximumFractionDigits: 2 })} %`;
  return `CLV ${value}${row.closingOdds === null ? '' : ` · close ${formatOdds(row.closingOdds)}`}`;
}

function resultLabel(row: ForwardResult): string {
  if (row.settlementResult === 'win') return 'Vinst';
  if (row.settlementResult === 'loss') return 'Förlust';
  if (row.settlementResult === 'push') return 'Push';
  return row.settlementResult ?? row.resultLoopStatus ?? '—';
}

interface ForwardResultTableProps {
  rows: ForwardResult[];
  ariaLabel?: string;
}

export function ForwardResultTable({ rows, ariaLabel = 'Forward-resultat' }: ForwardResultTableProps) {
  return (
    <section className="result-table" aria-label={ariaLabel}>
      {rows.map((row, index) => {
        const matchLabel = `${row.homeTeamName ?? 'Okänt lag'} – ${row.awayTeamName ?? 'Okänt lag'}`;
        return (
          <article className="result-row" key={row.resultLoopKey ?? `${row.matchKey ?? 'result'}:${index}`}>
            <div className="result-row__identity">
              <EntityLink kind="league" id={row.leagueKey} className="eyebrow">{row.leagueName ?? 'Liga saknas'}</EntityLink>
              <strong>
                <EntityLink kind="team" id={row.homeTeamKey}>{row.homeTeamName ?? 'Okänt lag'}</EntityLink>
                <span aria-hidden="true"> – </span>
                <EntityLink kind="team" id={row.awayTeamKey}>{row.awayTeamName ?? 'Okänt lag'}</EntityLink>
              </strong>
              <small>{[row.statKey, row.period, row.scope].filter(Boolean).join(' · ')}</small>
              <EntityLink kind="match" id={row.matchKey} className="quiet-link" ariaLabel={`Öppna ${matchLabel}`}>
                <ExternalLink size={13} aria-hidden="true" />Matchdetalj
              </EntityLink>
            </div>
            <span>{row.direction?.toUpperCase() ?? '—'} {row.lineValue ?? '—'}</span>
            <span>{resultLabel(row)}</span>
            <span>{units(row.roiUnits)}</span>
            <span>{officialClv(row)}</span>
          </article>
        );
      })}
    </section>
  );
}
