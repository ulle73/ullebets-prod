import { ArrowLeft, Clock3 } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { CheckpointTimeline } from '../components/CheckpointTimeline';
import { EntityLink } from '../components/EntityLink';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';
import { useMatchDetail } from '../data/queries';
import { formatKickoff } from '../domain/formatters';

function initials(name: string | null): string {
  if (!name) return '—';
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toLocaleUpperCase('sv-SE') ?? '').join('');
}

export function MatchDetailPage() {
  const { matchId } = useParams();
  const detail = useMatchDetail(matchId);

  if (detail.isLoading) return <StateNotice state="loading" title="Hämtar match" detail="Läser match, matchups och statistik." />;
  if (detail.isError || !detail.data) return <StateNotice state="failed" title="Matchen kunde inte läsas" detail="Matchen hittades inte eller datakällan kunde inte nås." />;

  const data = detail.data;
  const match = data.match;
  return (
    <div className="page-stack">
      <Link to="/oversikt" className="back-link"><ArrowLeft size={15} />Till översikt</Link>
      <section className="match-hero">
        <div className="match-hero__meta">
          <EntityLink kind="league" id={match.leagueKey}>{match.leagueName ?? 'Liga saknas'}</EntityLink>
          {match.startTime ? <span><Clock3 size={14} />{formatKickoff(match.startTime)}</span> : null}
        </div>
        <div className="team-versus">
          <EntityLink className="team-block" kind="team" id={match.homeTeamKey}>
            <span className="team-monogram">{initials(match.homeTeamName)}</span><strong>{match.homeTeamName ?? 'Okänt lag'}</strong>
          </EntityLink>
          <span className="versus-badge">VS</span>
          <EntityLink className="team-block team-block--right" kind="team" id={match.awayTeamKey}>
            <span className="team-monogram">{initials(match.awayTeamName)}</span><strong>{match.awayTeamName ?? 'Okänt lag'}</strong>
          </EntityLink>
        </div>
      </section>

      <section className="content-section">
        <div className="section-heading"><div><p className="eyebrow">Oddsflöde</p><h2>Checkpoint-tidslinje</h2></div></div>
        {data.checkpoints.length ? <CheckpointTimeline checkpoints={data.checkpoints} /> : <StateNotice state="empty" title="Inga checkpoints för matchen" detail="Saknade snapshots fylls inte i." />}
      </section>

      <section className="content-section">
        <div className="section-heading"><div><p className="eyebrow">Matchups</p><h2>Ranking för matchen</h2></div></div>
        {data.matchups.length ? <div className="detail-signal-grid">{data.matchups.map((row) => <SignalCard key={row.entryKey} signal={row} />)}</div> : <StateNotice state="empty" title="Ingen matchup-ranking" detail="Ingen matchup-ranking finns för matchen." />}
      </section>

      <section className="content-section">
        <div className="section-heading"><div><p className="eyebrow">Lagstatistik</p><h2>Lagjämförelse</h2></div></div>
        {data.teamStats.length === 0 ? <StateNotice state="empty" title="Lagstatistik saknas" detail="Inga värden uppskattas i frontend." /> : (
          <div className="stats-table" role="table" aria-label="Lagstatistik">
            <div className="stats-row stats-row--head" role="row"><span>Stat / period</span><span>{match.homeTeamName}</span><span>{match.awayTeamName}</span><span>Ligasnitt H / B</span></div>
            {data.teamStats.map((row) => (
              <div className="stats-row" role="row" key={`${row.statKey}:${row.period}`}>
                <strong>{row.statKey} · {row.period}</strong>
                <span>{row.homeValue?.toLocaleString('sv-SE') ?? '—'}{row.homeRank !== null ? ` (#${row.homeRank})` : ''}</span>
                <span>{row.awayValue?.toLocaleString('sv-SE') ?? '—'}{row.awayRank !== null ? ` (#${row.awayRank})` : ''}</span>
                <span>{row.homeLeagueAverage?.toLocaleString('sv-SE') ?? '—'} / {row.awayLeagueAverage?.toLocaleString('sv-SE') ?? '—'}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
