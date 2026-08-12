import type { ReactNode } from 'react';

export function PageHeader({ eyebrow, title, subtitle, aside }: { eyebrow: string; title: string; subtitle: string; aside?: ReactNode }) {
  return (
    <header className="product-page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {aside ? <div className="product-page-header__aside">{aside}</div> : null}
    </header>
  );
}
