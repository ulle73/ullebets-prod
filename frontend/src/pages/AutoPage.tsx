import { BrainCircuit, ExternalLink, ShieldCheck } from 'lucide-react';
import { EntityLink } from '../components/EntityLink';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useAuto } from '../data/queries';
import { formatExpectedRoi, formatOdds, formatProbability } from '../domain/formatters';

export function AutoPage() {
  const query = useAuto();
  if (query.isLoading) return <StateNotice state="loading" title="Läser Auto" detail="Hämtar registrerade forward-val." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Auto kunde inte läsas" detail="Försök igen när datakällan är tillgänglig." />;

  const { summary, selections } = query.data;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Registrerade forward-val" title="Auto" subtitle="Här visas val som redan registrerats av systemets urvalspolicy. Sidan skapar inga egna kandidater." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Registrerade val" value={summary.total} detail="Filtrerad mängd" tone="brand" icon={<ShieldCheck size={14} />} />
        <MetricTile label="Giltiga forward" value={summary.valid} detail="Giltiga för forward-utvärdering" icon={<BrainCircuit size={14} />} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Ej forward-performance" tone="warn" />
      </div>
      {selections.length === 0 ? <StateNotice state="empty" title="Inga registrerade forward-val" detail="Inga val matchar den aktuella läsvyn." /> : (
        <section className="product-section auto-list" aria-label="Forward-val">
          {selections.map((row, index) => {
            const matchLabel = `${row.homeTeamName ?? 'Okänt lag'} – ${row.awayTeamName ?? 'Okänt lag'}`;
            return (
              <article className="auto-row" key={row.selectionKey ?? `${row.matchKey ?? 'selection'}:${index}`}>
                <div>
                  <EntityLink kind="league" id={row.leagueKey} className="eyebrow">{row.leagueName ?? 'Liga saknas'}</EntityLink>
                  <h3>
                    <EntityLink kind="team" id={row.homeTeamKey}>{row.homeTeamName ?? 'Okänt lag'}</EntityLink>
                    <span aria-hidden="true"> – </span>
                    <EntityLink kind="team" id={row.awayTeamKey}>{row.awayTeamName ?? 'Okänt lag'}</EntityLink>
                  </h3>
                  <p>{[row.direction?.toUpperCase(), row.statKey, row.scope, row.period].filter(Boolean).join(' · ')}</p>
                  <EntityLink kind="match" id={row.matchKey} className="quiet-link" ariaLabel={`Öppna ${matchLabel}`}><ExternalLink size={13} aria-hidden="true" />Matchdetalj</EntityLink>
                </div>
                <div className="auto-row__metrics">
                  <span><small>Line</small><strong>{row.lineValue ?? '—'}</strong></span>
                  <span><small>Odds</small><strong>{formatOdds(row.selectedOdds)}</strong></span>
                  <span><small>Modell P</small><strong>{formatProbability(row.predictedWinProbability)}</strong></span>
                  <span><small>EV</small><strong>{formatExpectedRoi(row.expectedRoiUnits)}</strong></span>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
