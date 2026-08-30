import { useEffect, useMemo, useState } from 'react';

interface TeamCrestProps {
  name: string | null | undefined;
  imageUrl?: string | null;
  teamId?: string | number | null;
  teamKey?: string | null;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  className?: string;
}

function initials(name: string | null | undefined): string {
  if (!name) return '—';
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase('sv-SE') ?? '')
    .join('');
}

function filenameFromImageUrl(imageUrl: string | null | undefined): string | null {
  if (!imageUrl) return null;
  try {
    const pathname = new URL(imageUrl, 'https://ullebets.local').pathname;
    const filename = decodeURIComponent(pathname.split('/').filter(Boolean).pop() ?? '');
    return /^[a-z0-9._-]+\.(?:png|webp|jpe?g|svg)$/i.test(filename) ? filename : null;
  } catch {
    return null;
  }
}

function numericId(value: string | number | null | undefined): string | null {
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) return trimmed;
  const tagged = trimmed.match(/(?:^|[:/_-])(\d+)$/);
  return tagged?.[1] ?? null;
}

export function teamCrestSources({
  imageUrl,
  teamId,
  teamKey,
}: Pick<TeamCrestProps, 'imageUrl' | 'teamId' | 'teamKey'>): string[] {
  const sources: string[] = [];
  const add = (source: string | null | undefined) => {
    if (source && !sources.includes(source)) sources.push(source);
  };

  const filename = filenameFromImageUrl(imageUrl);
  if (filename) {
    add(`/images/teams/${filename}`);
    const stem = filename.replace(/\.(?:png|webp|jpe?g|svg)$/i, '');
    add(`/images/teams/${stem}.png`);
    add(`/images/teams/${stem}.webp`);
  }

  const id = numericId(teamId) ?? numericId(teamKey);
  if (id) {
    add(`/images/teams/${id}.png`);
    add(`/images/teams/${id}.webp`);
  }

  add(imageUrl);
  return sources;
}

export function TeamCrest({ name, imageUrl, teamId, teamKey, size = 'sm', className = '' }: TeamCrestProps) {
  const sources = useMemo(() => teamCrestSources({ imageUrl, teamId, teamKey }), [imageUrl, teamId, teamKey]);
  const sourceKey = sources.join('|');
  const [sourceIndex, setSourceIndex] = useState(0);

  useEffect(() => setSourceIndex(0), [sourceKey]);

  const source = sources[sourceIndex] ?? null;
  return (
    <span className={`team-crest team-crest--${size}${className ? ` ${className}` : ''}`} role="img" aria-label={`${name ?? 'Lag'} klubbmärke`}>
      <span className="team-crest__fallback" aria-hidden="true">{initials(name)}</span>
      {source ? (
        <img
          src={source}
          alt=""
          aria-hidden="true"
          onError={() => setSourceIndex((index) => index + 1)}
        />
      ) : null}
    </span>
  );
}
