const DEFAULT_MAX_SIZE = 500;

export function createCache({ ttlMs, maxSize = DEFAULT_MAX_SIZE } = {}) {
  const store = new Map();
  const defaultTtl = typeof ttlMs === "number" && ttlMs > 0 ? ttlMs : 0;

  function get(key) {
    const entry = store.get(key);
    if (!entry) return undefined;

    const { value, expiresAt } = entry;
    if (expiresAt && Date.now() > expiresAt) {
      store.delete(key);
      return undefined;
    }
    return value;
  }

  function set(key, value, ttlOverride) {
    const ttl = typeof ttlOverride === "number" && ttlOverride > 0 ? ttlOverride : defaultTtl;
    const expiresAt = ttl ? Date.now() + ttl : 0;

    if (store.size >= maxSize) {
      const oldestKey = store.keys().next().value;
      if (oldestKey !== undefined) {
        store.delete(oldestKey);
      }
    }

    store.set(key, { value, expiresAt });
  }

  function clear() {
    store.clear();
  }

  return { get, set, clear };
}
