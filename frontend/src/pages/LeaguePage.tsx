import { ExternalLink } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { EntityLink } from '../components/EntityLink';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useLeague } from '../data/queries';
import { formatKickoff } from '../domain/formatters';

export function LeaguePage() {
  const { leagueId } = useParams();
  const query = useLeague(leagueId);

  if (query.isLoading) return <StateNotice state="loading" title="Hämtar liga" detail="Läser liga, lag och matcher." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Ligan kunde inte hämtas" detail="Kontrollera att ligan fortfarande finns i datakällan." />;

  const { league, teams, matches } = query.data;
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={[league.country, league.seasonId].filter((value) => value !== null && value !== '').join(' · ') || 'Liga'}
        title={league.leagueName ?? 'Okänd liga'}
        subtitle={`${teams.length} lag · ${matches.length} matcher i aktuell läsvy`}
      />

      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Lag</p><h2>Lag i ligan</h2></div></div>
        {teams.length === 0 ? <StateNotice state="empty" title="Inga lag hittades" detail="Inga support_teams finns för ligan." /> : (
          <div className="entity-grid">
            {teams.map((team) => (
              <EntityLink kind="team" id={team.teamKey} className="entity-card" key={team.teamKey}>
                <strong>{team.teamName ?? team.teamKey}</strong>
                {team.optaRank !== null ? <span>Opta #{team.optaRank}</span> : <span>Lagprofil</span>}
              </EntityLink>
            ))}
          </div>
        )}
      </section>

      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Matcher</p><h2>Matcher</h2></div></div>
        {matches.length === 0 ? <StateNotice state="empty" title="Inga matcher hittades" detail="Inga canonical fixtures finns för ligan i läsvyn." /> : (
          <div className="entity-list">
            {matches.map((match) => {
              const label = `${match.homeTeamName ?? 'Okänt lag'} – ${match.awayTeamName ?? 'Okänt lag'}`;
              return (
                <article className="entity-row" key={match.matchKey}>
                  <time dateTime={match.startTime ?? undefined}>{match.startTime ? formatKickoff(match.startTime) : 'Tid saknas'}</time>
                  <div className="entity-row__main">
                    <EntityLink kind="team" id={match.homeTeamKey}>{match.homeTeamName ?? 'Okänt lag'}</EntityLink>
                    <span aria-hidden="true"> – </span>
                    <EntityLink kind="team" id={match.awayTeamKey}>{match.awayTeamName ?? 'Okänt lag'}</EntityLink>
                  </div>
                  {match.homeScore !== null && match.awayScore !== null ? <strong>{match.homeScore}–{match.awayScore}</strong> : null}
                  <EntityLink kind="match" id={match.matchKey} className="quiet-link" ariaLabel={`Öppna ${label}`}>
                    <ExternalLink size={14} aria-hidden="true" />
                    <span>Match</span>
                  </EntityLink>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
