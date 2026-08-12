export interface WatchReference {
  kind: 'match' | 'signal';
  id: string;
}

const STORAGE_KEY = 'ullebets.watchlist.v1';
const LEGACY_STORAGE_KEYS = ['ullebets.style-1.watchlist'] as const;

function isWatchReference(value: unknown): value is WatchReference {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return (candidate.kind === 'match' || candidate.kind === 'signal') && typeof candidate.id === 'string' && candidate.id.trim().length > 0;
}

function parseReferences(raw: string | null): WatchReference[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isWatchReference).map(({ kind, id }) => ({ kind, id: id.trim() }));
  } catch {
    return [];
  }
}

export function readWatchlist(): WatchReference[] {
  const current = parseReferences(window.localStorage.getItem(STORAGE_KEY));
  if (current.length) return current;

  for (const legacyKey of LEGACY_STORAGE_KEYS) {
    const legacy = parseReferences(window.localStorage.getItem(legacyKey));
    if (!legacy.length) continue;
    writeWatchlist(legacy);
    window.localStorage.removeItem(legacyKey);
    return legacy;
  }
  return [];
}

export function writeWatchlist(references: WatchReference[]): void {
  const safe = references
    .filter(isWatchReference)
    .map(({ kind, id }) => ({ kind, id: id.trim() }));
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(safe));
}
