export function sharedDateSearch(search: string): string {
  const current = new URLSearchParams(search);
  const date = current.get('date')?.trim();
  if (!date) return '';
  const shared = new URLSearchParams({ date });
  return `?${shared.toString()}`;
}
