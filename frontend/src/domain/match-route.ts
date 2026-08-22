const sourceMatchKey = /^sofascore:(.+)$/iu;

export function publicMatchId(matchKey: string): string {
  const sourceMatch = sourceMatchKey.exec(matchKey);
  return sourceMatch ? `match-${sourceMatch[1]}` : matchKey;
}

export function matchDetailPath(matchKey: string): string {
  return `/matcher/${encodeURIComponent(publicMatchId(matchKey))}`;
}
