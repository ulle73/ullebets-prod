import { BrainCircuit, ShieldCheck } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useAuto } from '../data/queries';
import { formatExpectedRoi, formatOdds, formatProbability } from '../domain/formatters';

export function AutoPage() {
  const query = useAuto();
  if (query.isLoading) return <StateNotice state="loading" title="Läser Auto" detail="Hämtar registrerade forward_bets från V2." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Auto kunde inte läsas" detail="Ingen fallbacklista visas." />;

  const valid = query.data.selections.filter((row) => row.validForForwardEvaluation === true && !row.invalidForModel);
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Registrerade forward-val" title="Auto" subtitle="Listan kommer direkt från V2 forward_bets. Frontend reproducerar inte urvalspolicyn." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Persistenta val" value={query.data.count} detail="forward_bets" tone="brand" icon={<ShieldCheck size={14} />} />
        <MetricTile label="Giltiga forward" value={valid.length} detail="valid_for_forward_evaluation" icon={<BrainCircuit size={14} />} />
        <MetricTile label="Exkluderade" value={query.data.selections.length - valid.length} detail="Ogiltig/utanför modell" tone="warn" />
      </div>
      {query.data.selections.length === 0 ? <StateNotice state="empty" title="Inga registrerade forward-val" detail="V2 returnerade inga forward_bets. Frontend skapar inga egna kandidater." /> : (
        <section className="product-section auto-list">
          {query.data.selections.map((row, index) => (
            <article className="auto-row" key={row.selectionKey ?? `${row.matchKey ?? 'selection'}:${index}`}>
              <div><span className="eyebrow">{row.leagueName ?? row.modelId ?? 'Forward'}</span><h3>{row.homeTeamName && row.awayTeamName ? `${row.homeTeamName} – ${row.awayTeamName}` : row.matchKey ?? 'Match saknas'}</h3><p>{[row.direction, row.statKey, row.scope, row.period].filter(Boolean).join(' · ')}</p></div>
              <div className="auto-row__metrics"><span><small>Line</small><strong>{row.lineValue ?? '—'}</strong></span><span><small>Odds</small><strong>{formatOdds(row.selectedOdds)}</strong></span><span><small>Modell P</small><strong>{formatProbability(row.predictedWinProbability)}</strong></span><span><small>EV</small><strong>{formatExpectedRoi(row.expectedRoiUnits)}</strong></span></div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
