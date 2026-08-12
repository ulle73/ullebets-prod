import { Bookmark, BookmarkPlus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { EntityLink } from '../components/EntityLink';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useDashboard, useMatches } from '../data/queries';
import { readWatchlist, writeWatchlist, type WatchReference } from '../data/watchlist-storage';
import { formatKickoff } from '../domain/formatters';

export function WatchlistPage() {
  const [items, setItems] = useState<WatchReference[]>(() => readWatchlist());
  const dashboard = useDashboard();
  const savedMatchIds = useMemo(() => items.filter((item) => item.kind === 'match').map((item) => item.id), [items]);
  const resolvedMatches = useMatches(savedMatchIds);
  const resolvedById = new Map((resolvedMatches.data?.matches ?? []).map((match) => [match.matchKey, match]));

  const update = (next: WatchReference[]) => {
    writeWatchlist(next);
    setItems(next);
  };
  const addMatch = (id: string) => {
    if (items.some((item) => item.kind === 'match' && item.id === id)) return;
    update([...items, { kind: 'match', id }]);
  };

  const availableMatches = dashboard.data?.matches ?? [];
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Personlig vy" title="Watchlist" subtitle="Endast stabila identifierare sparas lokalt. Aktuell matchdata hämtas på nytt." aside={<span className="watch-count"><Bookmark size={14} />{items.length}</span>} />
      {resolvedMatches.isError ? <StateNotice state="failed" title="Bevakade matcher kunde inte hämtas" detail="Dina sparade identifierare ligger kvar och kan hämtas igen senare." /> : null}
      {items.length === 0 ? <StateNotice state="empty" title="Ingen bevakning ännu" detail="Välj en match nedan för att lägga till den." /> : (
        <section className="watch-list" aria-label="Bevakade objekt">
          {items.map((item) => {
            const match = item.kind === 'match' ? resolvedById.get(item.id) : undefined;
            const waitingForMatch = item.kind === 'match' && resolvedMatches.isLoading;
            return (
              <article className="watch-row" key={`${item.kind}:${item.id}`}>
                <div>
                  <span className="watch-row__kind">{item.kind === 'match' ? 'Match' : 'Signal'}</span>
                  {match ? (
                    <>
                      <strong><EntityLink kind="match" id={match.matchKey}>{match.homeTeamName ?? 'Okänt lag'} – {match.awayTeamName ?? 'Okänt lag'}</EntityLink></strong>
                      <small>
                        <EntityLink kind="league" id={match.leagueKey}>{match.leagueName ?? 'Liga saknas'}</EntityLink>
                        {' · '}{match.startTime ? formatKickoff(match.startTime) : 'Tid saknas'}
                      </small>
                    </>
                  ) : (
                    <><strong>{item.id}</strong><small>{waitingForMatch ? 'Hämtar aktuell matchdata…' : item.kind === 'match' ? 'Matchen kunde inte lösas i aktuell datakälla' : 'Signalreferens'}</small></>
                  )}
                </div>
                <button className="icon-button" type="button" aria-label={`Ta bort ${item.id}`} onClick={() => update(items.filter((candidate) => !(candidate.kind === item.kind && candidate.id === item.id)))}><Trash2 size={16} /></button>
              </article>
            );
          })}
        </section>
      )}
      {dashboard.isError ? <StateNotice state="failed" title="Dagens matcher kunde inte hämtas" detail="Watchlistens sparade matcher påverkas inte." /> : null}
      {availableMatches.length ? (
        <section className="product-section">
          <div className="section-heading"><div><p className="eyebrow">Dagens matcher</p><h2>Lägg till bevakning</h2></div></div>
          <div className="watch-list">{availableMatches.map((match) => (
            <article className="watch-row" key={match.matchKey}>
              <div>
                <strong><EntityLink kind="match" id={match.matchKey}>{match.homeTeamName ?? 'Okänt lag'} – {match.awayTeamName ?? 'Okänt lag'}</EntityLink></strong>
                <small><EntityLink kind="league" id={match.leagueKey}>{match.leagueName ?? 'Liga saknas'}</EntityLink></small>
              </div>
              <button className="primary-button" type="button" onClick={() => addMatch(match.matchKey)}><BookmarkPlus size={15} />Bevaka</button>
            </article>
          ))}</div>
        </section>
      ) : null}
    </div>
  );
}
