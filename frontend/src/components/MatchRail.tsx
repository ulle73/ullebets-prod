import { CalendarDays, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatKickoff } from '../domain/formatters';
import type { MatchSummary } from '../domain/types';

interface MatchRailProps {
  matches: MatchSummary[];
  compact?: boolean;
}

export function MatchRail({ matches, compact = false }: MatchRailProps) {
  const grouped = matches.reduce<Map<string, MatchSummary[]>>((groups, match) => {
    const leagueMatches = groups.get(match.leagueName) ?? [];
    leagueMatches.push(match);
    groups.set(match.leagueName, leagueMatches);
    return groups;
  }, new Map());

  return (
    <section className={`match-rail${compact ? ' match-rail--compact' : ''}`} aria-label="Dagens matcher">
      <div className="match-rail__header">
        <div>
          <p className="eyebrow">Matcher</p>
          <h1>Dagens matcher</h1>
        </div>
        <span className="count-chip">{matches.length}</span>
      </div>

      <label className="date-control">
        <CalendarDays size={16} aria-hidden="true" />
        <span className="sr-only">Datum</span>
        <input type="date" defaultValue="2026-08-08" />
      </label>

      <label className="search-control">
        <Search size={16} aria-hidden="true" />
        <span className="sr-only">Sök lag eller liga</span>
        <input type="search" placeholder="Sök lag eller liga" />
      </label>

      <div className="segmented" aria-label="Matchfilter">
        <button type="button" className="is-active">Alla</button>
        <button type="button">Kommande</button>
        <button type="button">Resultat</button>
      </div>

      <div className="league-list">
        {Array.from(grouped.entries()).map(([league, leagueMatches]) => (
          <section key={league} className="league-group">
            <div className="league-group__title">
              <span className="league-mark" aria-hidden="true">B</span>
              <h2>{league}</h2>
            </div>
            <div className="match-list">
              {leagueMatches.map((match) => (
                <Link className="match-row" to={`/matcher/${match.matchKey}`} key={match.matchKey}>
                  <time dateTime={match.startTime}>{formatKickoff(match.startTime)}</time>
                  <span className="match-row__teams">
                    <strong>{match.homeTeamName}</strong>
                    <span className="match-row__versus">–</span>
                    <strong>{match.awayTeamName}</strong>
                  </span>
                  <span className={`status-dot status-dot--${match.status}`} aria-label={match.status === 'finished' ? 'Spelad' : 'Kommande'} />
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
