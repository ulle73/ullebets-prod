import { CircleSlash2, CircleX, ExternalLink, Trophy } from 'lucide-react';
import { EntityLink } from '../components/EntityLink';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useResults } from '../data/queries';
import { formatOdds } from '../domain/formatters';

function units(value: number | null): string {
  if (value === null) return '—';
  return `${value > 0 ? '+' : ''}${value.toLocaleString('sv-SE', { maximumFractionDigits: 2 })} u`;
}

function clv(value: number | null, official: boolean): string {
  if (!official || value === null) return 'CLV saknas';
  return `${value > 0 ? '+' : ''}${value.toLocaleString('sv-SE', { maximumFractionDigits: 2 })} %`;
}

export function ResultsLoopPage() {
  const query = useResults();
  if (query.isLoading) return <StateNotice state="loading" title="Läser resultatloop" detail="Hämtar registrerade forward-resultat." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Resultatloop kunde inte läsas" detail="Försök igen när datakällan är tillgänglig." />;

  const { summary, rows } = query.data;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Forward-resultat" title="Resultatloop" subtitle="Settlement, exclusions och closing-information visas från registrerade resultat." />
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Giltigt avgjorda" value={summary.settled} detail={`${summary.pushes} push`} tone="brand" />
        <MetricTile label="Vinster" value={summary.wins} detail="Settled" tone="good" icon={<Trophy size={14} />} />
        <MetricTile label="Förluster" value={summary.losses} detail="Settled" tone="bad" icon={<CircleX size={14} />} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Kvar för audit" tone="warn" icon={<CircleSlash2 size={14} />} />
      </div>
      {rows.length === 0 ? <StateNotice state="empty" title="Inga forward-resultat" detail="Inga resultat matchar den aktuella läsvyn." /> : (
        <section className="result-table" aria-label="Forward results">
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
                  <EntityLink kind="match" id={row.matchKey} className="quiet-link" ariaLabel={`Öppna ${matchLabel}`}><ExternalLink size={13} aria-hidden="true" />Matchdetalj</EntityLink>
                </div>
                <span>{row.direction?.toUpperCase() ?? '—'} {row.lineValue ?? '—'}</span>
                <span>{row.settlementResult ?? row.resultLoopStatus ?? '—'}</span>
                <span>{units(row.roiUnits)}</span>
                <span>{row.officialClv ? `${clv(row.clvPct, true)} · close ${formatOdds(row.closingOdds)}` : clv(null, false)}</span>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
