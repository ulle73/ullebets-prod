import * as Dialog from '@radix-ui/react-dialog';
import { Activity, BrainCircuit, Menu, X } from 'lucide-react';
import type { PropsWithChildren } from 'react';
import { Link } from 'react-router-dom';
import { previewMatches } from '../data/preview-data';
import { MatchRail } from './MatchRail';
import { TopNav } from './TopNav';

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <aside className="desktop-rail"><MatchRail matches={previewMatches} /></aside>
      <section className="workspace-shell">
        <header className="workspace-header">
          <div className="brand-row">
            <Link className="brand" to="/oversikt" aria-label="Ullebets översikt"><span className="brand__mark">U</span><span>ULLEBETS</span></Link>
            <span className="preview-badge">Förhandsvisning</span>
          </div>
          <div className="workspace-header__actions">
            <nav className="utility-nav" aria-label="Verktyg">
              <Link to="/modell"><BrainCircuit size={14} aria-hidden="true" /><span>Modell & proof</span></Link>
              <Link to="/systemstatus"><Activity size={14} aria-hidden="true" /><span>Systemstatus</span></Link>
            </nav>
            <div className="mobile-menu">
              <Dialog.Root>
                <Dialog.Trigger asChild><button type="button" className="icon-button" aria-label="Öppna matcher"><Menu size={20} /></button></Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="drawer-overlay" />
                  <Dialog.Content className="drawer-content" aria-describedby={undefined}>
                    <Dialog.Title className="sr-only">Dagens matcher</Dialog.Title>
                    <Dialog.Close asChild><button type="button" className="drawer-close" aria-label="Stäng matcher"><X size={20} /></button></Dialog.Close>
                    <MatchRail matches={previewMatches} compact />
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
            </div>
          </div>
        </header>
        <TopNav />
        <main className="workspace">{children}</main>
      </section>
    </div>
  );
}
