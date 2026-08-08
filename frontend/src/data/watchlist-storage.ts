export interface WatchReference {
  kind: 'match' | 'signal';
  id: string;
}

const STORAGE_KEY = 'ullebets.style-1.watchlist';

function isWatchReference(value: unknown): value is WatchReference {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return (candidate.kind === 'match' || candidate.kind === 'signal') && typeof candidate.id === 'string';
}

export function readWatchlist(): WatchReference[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isWatchReference).map(({ kind, id }) => ({ kind, id }));
  } catch {
    return [];
  }
}

export function writeWatchlist(references: WatchReference[]): void {
  const safe = references.map(({ kind, id }) => ({ kind, id }));
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(safe));
}
