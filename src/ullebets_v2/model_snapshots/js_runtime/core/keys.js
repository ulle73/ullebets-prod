/**
 * @fileoverview Core key generation utilities for the Ullebets platform.
 * These functions generate unique identifiers for bets, combos, matches, and lines.
 * 
 * CRITICAL: These key formats are used for database lookups and MUST remain stable.
 * Any changes to the key format will break existing data relationships.
 * 
 * @module lib/core/keys
 */

/**
 * Builds a unique bet key from bet parameters.
 * 
 * The bet key is a pipe-separated string used to uniquely identify bets across the system.
 * Format: `matchId|homeTeam|awayTeam|stat|scope|period|direction|line|form|groundType`
 * 
 * @param {Object} params - Bet parameters
 * @param {string|number} [params.matchId] - Match identifier
 * @param {string} params.homeTeam - Home team name
 * @param {string} params.awayTeam - Away team name
 * @param {string} params.stat - Statistic type (e.g., 'shotsOnGoal', 'cornerKicks')
 * @param {string} [params.scope='total'] - Scope ('home', 'away', or 'total')
 * @param {string} [params.period='ALL'] - Period ('ALL', '1ST', '2ND')
 * @param {number} params.line - The line value (e.g., 2.5, 10.5)
 * @param {boolean} params.over - True for 'over', false for 'under'
 * @param {string} [params.form=''] - Form filter (e.g., 'all', 'home', 'away')
 * @param {boolean} [params.neutralGround=false] - Whether match is on neutral ground
 * @returns {string} Pipe-separated bet key
 * 
 * @example
 * buildBetKey({
 *   matchId: '12345',
 *   homeTeam: 'Arsenal',
 *   awayTeam: 'Chelsea',
 *   stat: 'cornerKicks',
 *   scope: 'total',
 *   period: 'ALL',
 *   line: 10.5,
 *   over: true,
 *   form: 'all',
 *   neutralGround: false
 * })
 * // Returns: "12345|arsenal|chelsea|cornerKicks|total|ALL|over|10.5|all|H"
 */
export function buildBetKey({
  matchId,
  homeTeam,
  awayTeam,
  stat,
  scope,
  period,
  line,
  over,
  form,
  neutralGround,
}) {
  const parts = [
    matchId != null ? String(matchId) : "",
    String(homeTeam || "").toLowerCase().trim(),
    String(awayTeam || "").toLowerCase().trim(),
    stat ?? "",
    scope ?? "total",
    period ?? "ALL",
    over ? "over" : "under",
    Number(line),
    form ?? "",
    neutralGround ? "N" : "H",
  ];
  return parts.join("|");
}

/**
 * Builds a combo ID from an array of bet keys.
 * 
 * The combo ID is created by sorting bet keys alphabetically and joining with '@@'.
 * This ensures that combos with the same bets (regardless of order) have the same ID.
 * 
 * @param {string[]} betKeys - Array of bet keys to combine
 * @returns {string} Sorted, double-at-sign-separated combo ID
 * 
 * @example
 * buildComboId([
 *   "12345|arsenal|chelsea|cornerKicks|total|ALL|over|10.5|all|H",
 *   "12346|liverpool|everton|shotsOnGoal|total|ALL|under|4.5|all|H"
 * ])
 * // Returns: "12345|arsenal|chelsea|cornerKicks|total|ALL|over|10.5|all|H@@12346|liverpool|everton|shotsOnGoal|total|ALL|under|4.5|all|H"
 */
export function buildComboId(betKeys) {
  if (!Array.isArray(betKeys) || betKeys.length === 0) {
    return "";
  }
  // Sort alphabetically to ensure consistent IDs regardless of input order
  const sorted = [...betKeys].sort();
  return sorted.join("@@");
}

/**
 * Builds a match slug from team names and date.
 * 
 * Used for generating URL-friendly match identifiers and document IDs.
 * 
 * @param {string} homeTeam - Home team name
 * @param {string} awayTeam - Away team name
 * @param {string|Date} date - Match date (YYYY-MM-DD string or Date object)
 * @returns {string} Hyphen-separated slug
 * 
 * @example
 * buildMatchSlug("Arsenal FC", "Chelsea", "2024-11-28")
 * // Returns: "arsenal-fc-chelsea-2024-11-28"
 */
export function buildMatchSlug(homeTeam, awayTeam, date) {
  const slugify = (value) => {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "") // Remove diacritics
      .replace(/&/g, "and")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  };

  const dateStr = date instanceof Date 
    ? date.toISOString().split('T')[0] 
    : String(date).split('T')[0];

  return `${slugify(homeTeam)}-${slugify(awayTeam)}-${dateStr}`;
}

/**
 * Builds a line key for identifying specific betting lines.
 * 
 * Used for tracking individual lines within a match.
 * Format uses pipe `|` separator to match buildBetKey format.
 * 
 * @param {Object} params - Line parameters
 * @param {string|number} params.matchId - Match identifier
 * @param {string} params.statKey - Statistic type
 * @param {string} params.period - Period ('ALL', '1ST', '2ND')
 * @param {string} params.scope - Scope ('home', 'away', 'total')
 * @param {string} params.direction - Direction ('over' or 'under')
 * @returns {string} Pipe-separated line key
 * 
 * @example
 * buildLineKey({
 *   matchId: '12345',
 *   statKey: 'cornerKicks',
 *   period: 'ALL',
 *   scope: 'total',
 *   direction: 'over'
 * })
 * // Returns: "12345|cornerKicks|ALL|total|over"
 */
export function buildLineKey({ matchId, statKey, period, scope, direction }) {
  const parts = [
    matchId != null ? String(matchId) : "",
    statKey ?? "",
    period ?? "ALL",
    scope ?? "total",
    direction ?? "over",
  ];
  return parts.join("|");
}

/**
 * Normalizes a matchId to string format, handling various input types.
 * 
 * Helper function for consistent ID formatting across the system.
 * 
 * @param {string|number|null|undefined} id - The ID to normalize
 * @returns {string} Normalized string ID, or empty string if invalid
 * 
 * @example
 * normalizeStringId(12345) // Returns: "12345"
 * normalizeStringId("abc") // Returns: "abc"
 * normalizeStringId(null)  // Returns: ""
 */
export function normalizeStringId(id) {
  if (id == null) return "";
  return String(id).trim();
}
