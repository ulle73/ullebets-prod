import { Bookmark, BookmarkPlus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useDashboard } from '../data/queries';
import { readWatchlist, writeWatchlist, type WatchReference } from '../data/watchlist-storage';
import { formatKickoff } from '../domain/formatters';

export function WatchlistPage() {
  const [items, setItems] = useState<WatchReference[]>(() => readWatchlist());
  const dashboard = useDashboard();

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
      <PageHeader eyebrow="Personlig vy" title="Watchlist" subtitle="Endast identifierare sparas lokalt. Matchdata läses alltid från V2." aside={<span className="watch-count"><Bookmark size={14} />{items.length}</span>} />
      {dashboard.isError ? <StateNotice state="failed" title="V2 kunde inte läsas" detail="Watchlist-ID finns kvar lokalt men frontend visar ingen gammal matchdata." /> : null}
      {items.length === 0 ? <StateNotice state="empty" title="Ingen bevakning ännu" detail="Välj en aktuell V2-match nedan." /> : (
        <section className="watch-list">
          {items.map((item) => {
            const match = item.kind === 'match' ? availableMatches.find((candidate) => candidate.matchKey === item.id) : undefined;
            return (
              <article className="watch-row" key={`${item.kind}:${item.id}`}>
                <div><span className="watch-row__kind">{item.kind === 'match' ? 'Match' : 'Signal'}</span><strong>{match ? `${match.homeTeamName ?? 'Okänt lag'} – ${match.awayTeamName ?? 'Okänt lag'}` : item.id}</strong>{match ? <small>{match.leagueName ?? 'Liga saknas'} · {match.startTime ? formatKickoff(match.startTime) : 'Tid saknas'}</small> : <small>Inte i aktuell dashboard-response</small>}</div>
                <button className="icon-button" type="button" aria-label={`Ta bort ${item.id}`} onClick={() => update(items.filter((candidate) => !(candidate.kind === item.kind && candidate.id === item.id)))}><Trash2 size={16} /></button>
              </article>
            );
          })}
        </section>
      )}
      {availableMatches.length ? (
        <section className="product-section">
          <div className="section-heading"><div><p className="eyebrow">Matcher från V2</p><h2>Lägg till bevakning</h2></div></div>
          <div className="watch-list">{availableMatches.map((match) => (
            <article className="watch-row" key={match.matchKey}>
              <div><strong>{match.homeTeamName ?? 'Okänt lag'} – {match.awayTeamName ?? 'Okänt lag'}</strong><small>{match.leagueName ?? 'Liga saknas'}</small></div>
              <button className="primary-button" type="button" onClick={() => addMatch(match.matchKey)}><BookmarkPlus size={15} />Bevaka</button>
            </article>
          ))}</div>
        </section>
      ) : null}
    </div>
  );
}
