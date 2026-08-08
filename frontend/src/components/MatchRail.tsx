import { CalendarDays, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatKickoff } from '../domain/formatters';
import type { MatchSummary } from '../domain/types';

interface MatchRailProps {
  matches: MatchSummary[];
  selectedDate: string | null;
  onDateChange: (date: string) => void;
  loading?: boolean;
  failed?: boolean;
  compact?: boolean;
}

type StatusFilter = 'all' | 'upcoming' | 'live' | 'finished';

function statusBucket(status: string | null): Exclude<StatusFilter, 'all'> {
  const normalized = (status ?? '').toLowerCase();
  if (['finished', 'ended', 'cancelled', 'postponed'].some((value) => normalized.includes(value))) return 'finished';
  if (['live', 'inprogress', 'in_progress', '1st', '2nd', 'halftime'].some((value) => normalized.includes(value))) return 'live';
  return 'upcoming';
}

export function MatchRail({ matches, selectedDate, onDateChange, loading = false, failed = false, compact = false }: MatchRailProps) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const filteredMatches = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('sv-SE');
    return matches.filter((match) => {
      if (statusFilter !== 'all' && statusBucket(match.statusType) !== statusFilter) return false;
      if (!needle) return true;
      return [match.homeTeamName, match.awayTeamName, match.leagueName]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase('sv-SE').includes(needle));
    });
  }, [matches, search, statusFilter]);

  const grouped = filteredMatches.reduce<Map<string, MatchSummary[]>>((groups, match) => {
    const league = match.leagueName || 'Okänd liga';
    const leagueMatches = groups.get(league) ?? [];
    leagueMatches.push(match);
    groups.set(league, leagueMatches);
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
        ] as const).map(([value, label]) => (
          <button key={value} type="button" className={statusFilter === value ? 'is-active' : ''} onClick={() => setStatusFilter(value)}>{label}</button>
        ))}
      </div>

      {failed ? <p className="rail-state">Kunde inte läsa matcher från V2.</p> : null}
      {!failed && !loading && filteredMatches.length === 0 ? <p className="rail-state">Inga matcher för valt datum/filter.</p> : null}

      <div className="league-list">
        {Array.from(grouped.entries()).map(([league, leagueMatches]) => (
          <section key={league} className="league-group">
            <div className="league-group__title"><span className="league-mark" aria-hidden="true">•</span><h2>{league}</h2></div>
            <div className="match-list">
              {leagueMatches.map((match) => (
                <Link className="match-row" to={`/matcher/${encodeURIComponent(match.matchKey)}${selectedDate ? `?date=${encodeURIComponent(selectedDate)}` : ''}`} key={match.matchKey}>
                  <time dateTime={match.startTime ?? undefined}>{match.startTime ? formatKickoff(match.startTime) : '—'}</time>
                  <span className="match-row__teams">
                    <strong>{match.homeTeamName ?? 'Okänt lag'}</strong>
                    <span className="match-row__versus">–</span>
                    <strong>{match.awayTeamName ?? 'Okänt lag'}</strong>
                  </span>
                  <span className={`status-dot status-dot--${statusBucket(match.statusType)}`} aria-label={match.statusType ?? 'Okänd status'} />
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
