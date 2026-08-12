import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { Link } from 'react-router-dom';

export type EntityKind = 'match' | 'team' | 'league';

type EntityLinkProps = {
  kind: EntityKind;
  id: string | null | undefined;
  children: ReactNode;
  className?: string;
  ariaLabel?: string;
} & Omit<ComponentPropsWithoutRef<'span'>, 'children' | 'className'>;

function entityPath(kind: EntityKind, id: string): string {
  const encoded = encodeURIComponent(id);
  if (kind === 'match') return `/matcher/${encoded}`;
  if (kind === 'team') return `/lag/${encoded}`;
  return `/liga/${encoded}`;
}

export function EntityLink({ kind, id, children, className, ariaLabel, ...spanProps }: EntityLinkProps) {
  if (!id) {
    return <span className={className} {...spanProps}>{children}</span>;
  }

  return (
    <Link className={className} to={entityPath(kind, id)} aria-label={ariaLabel}>
      {children}
    </Link>
  );
}
