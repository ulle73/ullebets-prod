import { describe, expect, it } from 'vitest';
import { matchDetailPath, publicMatchId } from './match-route';

describe('public match routes', () => {
  it('replaces source-branded match keys with neutral public identifiers', () => {
    const publicId = publicMatchId('sofascore:16283044');

    expect(publicId).toBe('match-16283044');
    expect(publicId).not.toContain('sofascore');
    expect(matchDetailPath('sofascore:16283044')).toBe('/matcher/match-16283044');
  });

  it('retains already-neutral identifiers', () => {
    expect(matchDetailPath('m1')).toBe('/matcher/m1');
  });
});
