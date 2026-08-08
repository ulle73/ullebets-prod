import { beforeEach, describe, expect, it } from 'vitest';
import { readWatchlist, writeWatchlist } from './watchlist-storage';

describe('watchlist local persistence boundary', () => {
  beforeEach(() => window.localStorage.clear());

  it('persists identifiers only and strips accidental canonical/model fields', () => {
    writeWatchlist([
      { kind: 'match', id: 'gremio-sao-paulo', offeredOdds: 1.95, expectedRoiUnits: 0.13 } as never,
    ]);

    const raw = window.localStorage.getItem('ullebets.style-1.watchlist');
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toEqual([{ kind: 'match', id: 'gremio-sao-paulo' }]);
    expect(readWatchlist()).toEqual([{ kind: 'match', id: 'gremio-sao-paulo' }]);
  });
});
