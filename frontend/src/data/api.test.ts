import { describe, expect, it } from 'vitest';
import { buildApiUrl } from './api';
import { localDateKey } from './queries';

describe('buildApiUrl', () => {
  it('builds a read-only dashboard URL from caller-provided data', () => {
    expect(buildApiUrl('/dashboard', { date: '2026-08-09' })).toBe('/api/v1/dashboard?date=2026-08-09');
  });

  it('omits absent query values instead of inventing defaults', () => {
    expect(buildApiUrl('/dashboard', { date: undefined })).toBe('/api/v1/dashboard');
  });
});

describe('localDateKey', () => {
  it('derives the selected day from runtime local time instead of a product fixture', () => {
    expect(localDateKey(new Date(2031, 3, 5, 23, 30))).toBe('2031-04-05');
  });
});
