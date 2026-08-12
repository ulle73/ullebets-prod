import { Activity, CalendarDays, SlidersHorizontal } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';
import { useDashboard } from '../data/queries';

export function OverviewPage() {
  const [searchParams] = useSearchParams();
  const requestedDate = searchParams.get('date') || undefined;
  const dashboard = useDashboard(requestedDate);
  const [league, setLeague] = useState('all');
  const [stat, setStat] = useState('all');

  const matchups = useMemo(() => dashboard.data?.matchups ?? [], [dashboard.data?.matchups]);
  const leagues = useMemo(() => Array.from(new Set(matchups.map((row) => row.leagueName).filter((value): value is string => Boolean(value)))).sort(), [matchups]);
  const stats = useMemo(() => Array.from(new Map(matchups.filter((row) => row.statKey).map((row) => [row.statKey!, row.statLabel ?? row.statKey!])).entries()).sort((a, b) => a[1].localeCompare(b[1], 'sv')), [matchups]);
  const filtered = matchups.filter((row) => (league === 'all' || row.leagueName === league) && (stat === 'all' || row.statKey === stat));
  const over = filtered.filter((row) => row.condition === 'OVER');
  const under = filtered.filter((row) => row.condition === 'UNDER');

  if (dashboard.isLoading) {
    return <StateNotice state="loading" title="Hämtar dagens matcher" detail="Matchlistan och matchup-rankingen uppdateras." />;
  }
  if (dashboard.isError) {
    return <StateNotice state="failed" title="Dagens matcher kunde inte hämtas" detail="Försök igen om en stund. Ingen reservdata visas när källan inte kan nås." />;
  }

  const sourceLabel = dashboard.data?.matchupSource === 'computed_read_only'
    ? 'Aktuell matchup-ranking'
    : dashboard.data?.matchupSource === 'persisted'
      ? 'Matchup-ranking'
      : 'Ranking saknas';

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <p className="eyebrow">Översikt</p>
          <h2>Dagens matchups</h2>
          <p className="page-subtitle">Jämför dagens högst rankade OVER- och UNDER-matchups per stat, period och lagkontext.</p>
        </div>
        <div className="summary-strip" aria-label="Översiktsstatus">
          <span><CalendarDays size={14} />{dashboard.data.selectedDate}</span>
          <span><Activity size={14} />{dashboard.data.matches.length} matcher</span>
          <span>{sourceLabel}</span>
        </div>
      </section>

      {dashboard.data.matches.length === 0 ? (
        <StateNotice state="empty" title="Inga matcher för valt datum" detail="Välj ett annat datum för att se tillgängliga matcher." />
      ) : null}
      {dashboard.data.matches.length > 0 && matchups.length === 0 ? (
        <StateNotice state="empty" title="Matchup-ranking saknas" detail="Matcher finns för dagen, men det finns ännu inte tillräcklig data för en matchup-ranking." />
      ) : null}

      <div className="filter-toolbar">
        <span><SlidersHorizontal size={15} aria-hidden="true" />Filter</span>
        <select aria-label="Liga" value={league} onChange={(event) => setLeague(event.target.value)}>
          <option value="all">Alla ligor</option>
          {leagues.map((value) => <option value={value} key={value}>{value}</option>)}
        </select>
        <select aria-label="Stat" value={stat} onChange={(event) => setStat(event.target.value)}>
          <option value="all">Alla statstyper</option>
          {stats.map(([key, label]) => <option value={key} key={key}>{label}</option>)}
        </select>
      </div>

      <div className="signal-columns">
        <section className="signal-column">
          <header className="signal-column__header"><span className="signal-column__dot signal-column__dot--over" /><h3>Över – topp 20</h3><span>{over.length}</span></header>
          <div className="signal-list">{over.map((row) => <SignalCard key={row.entryKey} signal={row} />)}</div>
        </section>
        <section className="signal-column">
          <header className="signal-column__header"><span className="signal-column__dot signal-column__dot--under" /><h3>Under – topp 20</h3><span>{under.length}</span></header>
          <div className="signal-list">{under.map((row) => <SignalCard key={row.entryKey} signal={row} />)}</div>
        </section>
      </div>
    </div>
  );
}
