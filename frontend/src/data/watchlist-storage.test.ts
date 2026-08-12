import { beforeEach, describe, expect, it } from 'vitest';
import { readWatchlist, writeWatchlist } from './watchlist-storage';

describe('watchlist local persistence boundary', () => {
  beforeEach(() => window.localStorage.clear());

  it('persists identifiers only under a branch-independent versioned key', () => {
    writeWatchlist([
      { kind: 'match', id: 'gremio-sao-paulo', offeredOdds: 1.95, expectedRoiUnits: 0.13 } as never,
    ]);

    const raw = window.localStorage.getItem('ullebets.watchlist.v1');
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toEqual([{ kind: 'match', id: 'gremio-sao-paulo' }]);
    expect(readWatchlist()).toEqual([{ kind: 'match', id: 'gremio-sao-paulo' }]);
  });

  it('migrates the old style branch key without losing saved references', () => {
    window.localStorage.setItem('ullebets.style-1.watchlist', JSON.stringify([{ kind: 'match', id: 'old-match' }]));

    expect(readWatchlist()).toEqual([{ kind: 'match', id: 'old-match' }]);
    expect(window.localStorage.getItem('ullebets.style-1.watchlist')).toBeNull();
    expect(JSON.parse(window.localStorage.getItem('ullebets.watchlist.v1')!)).toEqual([{ kind: 'match', id: 'old-match' }]);
  });
});
