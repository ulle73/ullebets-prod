import { useParams } from 'react-router-dom';
import { EntityLink } from '../components/EntityLink';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useTeam } from '../data/queries';

export function TeamPage() {
  const { teamId } = useParams();
  const query = useTeam(teamId);
  if (query.isLoading) return <StateNotice state="loading" title="Hämtar lagprofil" detail="Läser lagets aktuella statistik." />;
  if (query.isError || !query.data) return <StateNotice state="empty" title="Lagprofil saknas" detail="Ingen lagprofil kunde hittas för identifieraren." />;

  const { team, league, contexts } = query.data;
  const context = contexts.home ?? contexts.away;
  const stats = context?.statistics.for ?? {};
  const leagueAverage = context?.statistics.leagueAverage?.for ?? {};
  const rows = Object.entries(stats).flatMap(([statKey, periods]) => {
    const current = periods.ALL;
    if (!current || current.value === null || current.value === undefined) return [];
    return [{ statKey, current, league: leagueAverage[statKey]?.ALL }];
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={league?.leagueName ?? 'Lagprofil'}
        title={team.teamName ?? team.teamKey}
        subtitle={context ? `${context.matchType ?? 'Profil'} · ${context.profileDate ?? 'aktuellt'}` : 'Ingen aktuell teamprofile'}
        aside={league ? <EntityLink kind="league" id={league.leagueKey} className="quiet-link">Öppna ligan</EntityLink> : undefined}
      />
      {!context ? <StateNotice state="empty" title="Teamprofile-data saknas" detail="Ingen home- eller away-profil finns för laget." /> : rows.length === 0 ? (
        <StateNotice state="empty" title="Statistik saknas i profilen" detail="Tomma statistikfält ersätts inte med uppskattningar." />
      ) : (
        <section className="stats-table" role="table" aria-label="Teamprofile statistik">
          <div className="stats-row stats-row--head" role="row"><span>Stat</span><span>Värde</span><span>Rank</span><span>Ligasnitt</span></div>
          {rows.map(({ statKey, current, league: leagueNode }) => (
            <div className="stats-row" role="row" key={statKey}>
              <strong>{statKey}</strong>
              <span>{current.value?.toLocaleString('sv-SE') ?? '—'}</span>
              <span>{current.rank !== null && current.rank !== undefined ? `#${current.rank}` : '—'}</span>
              <span>{leagueNode?.value?.toLocaleString('sv-SE') ?? '—'}</span>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
