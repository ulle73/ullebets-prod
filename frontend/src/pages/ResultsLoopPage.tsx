import { CircleSlash2, CircleX, Trophy } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useResults } from '../data/queries';

function text(row: Record<string, unknown>, key: string): string {
  const value = row[key];
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : '—';
}

export function ResultsLoopPage() {
  const query = useResults();
  if (query.isLoading) return <StateNotice state="loading" title="Läser resultatloop" detail="Hämtar forward_results från V2." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Resultatloop kunde inte läsas" detail="Ingen sparad frontend-snapshot används." />;

  const { summary, rows } = query.data;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="V2 forward_results" title="Resultatloop" subtitle="Settlement, exclusions och CLV visas från den persistenta resultatloopen." />
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Giltigt avgjorda" value={summary.settled} detail="valid_for_performance" tone="brand" />
        <MetricTile label="Vinster" value={summary.wins} detail="Settled" tone="good" icon={<Trophy size={14} />} />
        <MetricTile label="Förluster" value={summary.losses} detail="Settled" tone="bad" icon={<CircleX size={14} />} />
        <MetricTile label="Exkluderade" value={summary.excluded} detail="Kvar för audit" tone="warn" icon={<CircleSlash2 size={14} />} />
      </div>
      {rows.length === 0 ? <StateNotice state="empty" title="Inga forward_results" detail="V2 returnerade inga resultat. Frontend visar inget exempelutfall." /> : (
        <section className="result-table" aria-label="Forward results">
          {rows.map((row, index) => (
            <article className="result-row" key={text(row, 'result_loop_key') !== '—' ? text(row, 'result_loop_key') : String(index)}>
              <div><strong>{text(row, 'home_team_name')} – {text(row, 'away_team_name')}</strong><small>{text(row, 'league_name')} · {text(row, 'stat_key')} · {text(row, 'period')} · {text(row, 'scope')}</small></div>
              <span>{text(row, 'direction')} {text(row, 'line_value')}</span>
              <span>{text(row, 'settlement_result')}</span>
              <span>{text(row, 'roi_units')} u</span>
              <span>{text(row, 'clv_pct')}</span>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
