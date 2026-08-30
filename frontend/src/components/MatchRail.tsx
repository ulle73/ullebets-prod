import { CalendarDays, ExternalLink, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { matchPath, useLocation } from 'react-router-dom';
import { formatKickoff } from '../domain/formatters';
import { publicMatchId } from '../domain/match-route';
import type { MatchState, MatchSummary } from '../domain/types';
import { EntityLink } from './EntityLink';
import { TeamCrest } from './TeamCrest';

interface MatchRailProps {
  matches: MatchSummary[];
  selectedDate: string | null;
  onDateChange: (date: string) => void;
  loading?: boolean;
  failed?: boolean;
  compact?: boolean;
}

type StatusFilter = 'all' | 'upcoming' | 'live' | 'finished';

function matchesStatusFilter(state: MatchState, filter: StatusFilter): boolean {
  if (filter === 'all') return true;
  return state === filter;
}

export function MatchRail({ matches, selectedDate, onDateChange, loading = false, failed = false, compact = false }: MatchRailProps) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const location = useLocation();
  const matchRoute = matchPath('/matcher/:matchId', location.pathname);
  const activeMatchId = matchRoute?.params.matchId ? decodeURIComponent(matchRoute.params.matchId) : null;

  const filteredMatches = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('sv-SE');
    return matches.filter((match) => {
      if (!matchesStatusFilter(match.state, statusFilter)) return false;
      if (!needle) return true;
      return [match.homeTeamName, match.awayTeamName, match.leagueName]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase('sv-SE').includes(needle));
    });
  }, [matches, search, statusFilter]);

  const grouped = filteredMatches.reduce<Map<string, { leagueKey: string | null; matches: MatchSummary[] }>>((groups, match) => {
    const leagueName = match.leagueName || 'Okänd liga';
    const existing = groups.get(leagueName) ?? { leagueKey: match.leagueKey, matches: [] };
    existing.matches.push(match);
    groups.set(leagueName, existing);
    return groups;
  }, new Map());

  return (
    <section className={`match-rail${compact ? ' match-rail--compact' : ''}`} aria-label="Dagens matcher">
      <div className="match-rail__header">
        <div>
          <p className="eyebrow">Matcher</p>
          <h1>Dagens matcher</h1>
        </div>
        <span className="count-chip">{loading ? '…' : matches.length}</span>
      </div>

      <label className="date-control">
        <CalendarDays size={16} aria-hidden="true" />
        <span className="sr-only">Datum</span>
        <input type="date" value={selectedDate ?? ''} onChange={(event) => onDateChange(event.target.value)} />
      </label>

      <label className="search-control">
        <Search size={16} aria-hidden="true" />
        <span className="sr-only">Sök lag eller liga</span>
        <input type="search" placeholder="Sök lag eller liga" value={search} onChange={(event) => setSearch(event.target.value)} />
      </label>

      <div className="segmented" aria-label="Matchfilter">
        {([
          ['all', 'Alla'],
          ['upcoming', 'Kommande'],
          ['live', 'Pågår'],
          ['finished', 'Resultat'],
        ] as const).map(([filter, label]) => (
          <button key={filter} type="button" className={statusFilter === filter ? 'is-active' : ''} onClick={() => setStatusFilter(filter)}>{label}</button>
        ))}
      </div>

      {failed ? <p className="rail-state">Matcher kunde inte hämtas.</p> : null}
      {!failed && !loading && filteredMatches.length === 0 ? <p className="rail-state">Inga matcher för valt datum/filter.</p> : null}

      <div className="league-list">
        {Array.from(grouped.entries()).map(([leagueName, group]) => (
          <section key={leagueName} className="league-group">
            <div className="league-group__title">
              <span className="league-mark" aria-hidden="true">•</span>
              <h2><EntityLink kind="league" id={group.leagueKey}>{leagueName}</EntityLink></h2>
            </div>
            <div className="match-list">
              {group.matches.map((match) => {
                const matchLabel = `${match.homeTeamName ?? 'Okänt lag'} – ${match.awayTeamName ?? 'Okänt lag'}`;
                return (
                  <article className={`match-row${activeMatchId === publicMatchId(match.matchKey) ? ' is-active' : ''}`} key={match.matchKey}>
                    <time dateTime={match.startTime ?? undefined}>{match.startTime ? formatKickoff(match.startTime) : '—'}</time>
                    <span className="match-row__teams">
                      <span className="match-row__team">
                        <TeamCrest name={match.homeTeamName} imageUrl={match.homeTeamImageUrl} teamKey={match.homeTeamKey} size="xs" />
                        <strong><EntityLink kind="team" id={match.homeTeamKey}>{match.homeTeamName ?? 'Okänt lag'}</EntityLink></strong>
                      </span>
                      <span className="match-row__team">
                        <TeamCrest name={match.awayTeamName} imageUrl={match.awayTeamImageUrl} teamKey={match.awayTeamKey} size="xs" />
                        <strong><EntityLink kind="team" id={match.awayTeamKey}>{match.awayTeamName ?? 'Okänt lag'}</EntityLink></strong>
                      </span>
                    </span>
                    {match.state === 'finished' && match.homeScore !== null && match.awayScore !== null ? (
                      <span className="match-row__score" aria-label={`Slutresultat ${match.homeScore}–${match.awayScore}`}>{match.homeScore}–{match.awayScore}</span>
                    ) : (
                      <span className={`status-dot status-dot--${match.state}`} aria-label={match.state} />
                    )}
                    <EntityLink kind="match" id={match.matchKey} className="match-row__open" ariaLabel={`Öppna ${matchLabel}`}>
                      <ExternalLink size={14} aria-hidden="true" />
                    </EntityLink>
                  </article>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
