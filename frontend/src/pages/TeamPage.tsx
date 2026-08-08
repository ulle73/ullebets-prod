import { useParams } from 'react-router-dom';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useTeam } from '../data/queries';

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function value(node: Record<string, unknown>, key: string): string {
  const item = node[key];
  return typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean' ? String(item) : '—';
}

export function TeamPage() {
  const { teamId } = useParams();
  const query = useTeam(teamId);
  if (query.isLoading) return <StateNotice state="loading" title="Läser lagprofil" detail="Hämtar teamprofiles från V2." />;
  if (query.isError || !query.data || query.data.profiles.length === 0) return <StateNotice state="empty" title="Lagprofil saknas" detail="Ingen testfixture eller reservprofil visas." />;

  const profile = query.data.profiles[0]!;
  const meta = object(profile.meta);
  const stats = object(object(profile.statistics).for);
  const leagueAverage = object(object(object(profile.statistics).leagueAverage).for);
  const rows = Object.entries(stats).flatMap(([statKey, periodsValue]) => {
    const periods = object(periodsValue);
    const all = object(periods.ALL);
    if (all.value === null || all.value === undefined) return [];
    const leagueAll = object(object(leagueAverage[statKey]).ALL);
    return [{ statKey, current: all, league: leagueAll }];
  });

  return (
    <div className="page-stack">
      <PageHeader eyebrow={value(meta, 'leagueName')} title={value(meta, 'lagnamn')} subtitle={`${value(profile, 'match_type')} · profil ${value(profile, 'profile_date')}`} />
      {rows.length === 0 ? <StateNotice state="empty" title="Statistik saknas i profilen" detail="Frontend fyller inte tomma teamprofile-fält." /> : (
        <section className="stats-table" role="table" aria-label="Teamprofile statistik">
          <div className="stats-row stats-row--head" role="row"><span>Stat</span><span>Värde</span><span>Rank</span><span>Ligasnitt</span></div>
          {rows.map(({ statKey, current, league }) => (
            <div className="stats-row" role="row" key={statKey}><strong>{statKey}</strong><span>{value(current, 'value')}</span><span>{value(current, 'rank')}</span><span>{value(league, 'value')}</span></div>
          ))}
        </section>
      )}
    </div>
  );
}
