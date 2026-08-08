import { Bookmark, BookmarkPlus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { previewMatches } from '../data/preview-data';
import { readWatchlist, writeWatchlist, type WatchReference } from '../data/watchlist-storage';
import { formatKickoff } from '../domain/formatters';

export function WatchlistPage() {
  const [items, setItems] = useState<WatchReference[]>(() => readWatchlist());
  const previewMatch = previewMatches[0]!;

  const update = (next: WatchReference[]) => {
    writeWatchlist(next);
    setItems(next);
  };

  const addPreviewMatch = () => {
    if (items.some((item) => item.kind === 'match' && item.id === previewMatch.matchKey)) return;
    update([...items, { kind: 'match', id: previewMatch.matchKey }]);
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Personlig vy" title="Watchlist" subtitle="Bevakning i Style-1 sparar bara identifierare och UI-preferenser lokalt — aldrig odds, resultat eller modellvärden." aside={<span className="watch-count"><Bookmark size={14} />{items.length}</span>} />
      <StateNotice state="ready" title="Local-only i denna branch" detail="Watchlist lagrar bara identifierare. All kanonisk match-, odds- och modelldata ska alltid läsas på nytt från read-modellen." />
      {items.length === 0 ? (
        <section className="empty-product-card">
          <Bookmark size={26} aria-hidden="true" />
          <h2>Ingen bevakning ännu</h2>
          <p>Lägg till previewmatchen för att testa layout och lokal persistens utan att skapa en backend-write.</p>
          <button className="primary-button" type="button" onClick={addPreviewMatch}><BookmarkPlus size={15} />Bevaka Grêmio – São Paulo</button>
        </section>
      ) : (
        <section className="watch-list">
          {items.map((item) => {
            const match = item.kind === 'match' ? previewMatches.find((candidate) => candidate.matchKey === item.id) : undefined;
            return (
              <article className="watch-row" key={`${item.kind}:${item.id}`}>
                <div><span className="watch-row__kind">{item.kind === 'match' ? 'Match' : 'Signal'}</span><strong>{match ? `${match.homeTeamName} – ${match.awayTeamName}` : item.id}</strong>{match ? <small>{match.leagueName} · {formatKickoff(match.startTime)}</small> : null}</div>
                <button className="icon-button" type="button" aria-label={`Ta bort ${item.id}`} onClick={() => update(items.filter((candidate) => !(candidate.kind === item.kind && candidate.id === item.id)))}><Trash2 size={16} /></button>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
