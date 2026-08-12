import * as Dialog from '@radix-ui/react-dialog';
import { Activity, BrainCircuit, Menu, X } from 'lucide-react';
import type { PropsWithChildren } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { useDashboard } from '../data/queries';
import { sharedDateSearch } from '../domain/navigation';
import { MatchRail } from './MatchRail';
import { TopNav } from './TopNav';

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedDate = searchParams.get('date') || undefined;
  const dashboard = useDashboard(requestedDate);
  const matches = dashboard.data?.matches ?? [];
  const selectedDate = dashboard.data?.selectedDate ?? requestedDate ?? '';
  const sharedSearch = sharedDateSearch(location.search);

  const changeDate = (date: string) => {
    const next = new URLSearchParams(searchParams);
    if (date) next.set('date', date);
    else next.delete('date');
    setSearchParams(next, { replace: false });
  };

  const rail = (
    <MatchRail
      matches={matches}
      selectedDate={selectedDate}
      onDateChange={changeDate}
      loading={dashboard.isLoading}
      failed={dashboard.isError}
    />
  );

  return (
    <>
      <a className="skip-link" href="#main-content">Hoppa till huvudinnehåll</a>
      <div className="app-shell">
        <aside className="desktop-rail">{rail}</aside>
        <section className="workspace-shell">
          <header className="workspace-header">
            <div className="brand-row">
              <Link className="brand" to={`/oversikt${sharedSearch}`} aria-label="Ullebets översikt"><span className="brand__mark">U</span><span>ULLEBETS</span></Link>
              <span className="preview-badge">Live</span>
            </div>
            <div className="workspace-header__actions">
              <nav className="utility-nav" aria-label="Verktyg">
                <Link to={`/modell${sharedSearch}`}><BrainCircuit size={14} aria-hidden="true" /><span>Modell & proof</span></Link>
                <Link to={`/systemstatus${sharedSearch}`}><Activity size={14} aria-hidden="true" /><span>Systemstatus</span></Link>
              </nav>
              <div className="mobile-menu">
                <Dialog.Root>
                  <Dialog.Trigger asChild><button type="button" className="icon-button" aria-label="Öppna matcher"><Menu size={20} aria-hidden="true" /></button></Dialog.Trigger>
                  <Dialog.Portal>
                    <Dialog.Overlay className="drawer-overlay" />
                    <Dialog.Content className="drawer-content" aria-describedby={undefined}>
                      <Dialog.Title className="sr-only">Dagens matcher</Dialog.Title>
                      <Dialog.Close asChild><button type="button" className="drawer-close" aria-label="Stäng matcher"><X size={20} aria-hidden="true" /></button></Dialog.Close>
                      {rail}
                      <nav className="mobile-utility-nav" aria-label="Verktyg i mobil">
                        <Dialog.Close asChild><Link to={`/modell${sharedSearch}`}><BrainCircuit size={15} aria-hidden="true" /><span>Modell & proof</span></Link></Dialog.Close>
                        <Dialog.Close asChild><Link to={`/systemstatus${sharedSearch}`}><Activity size={15} aria-hidden="true" /><span>Systemstatus</span></Link></Dialog.Close>
                      </nav>
                    </Dialog.Content>
                  </Dialog.Portal>
                </Dialog.Root>
              </div>
            </div>
          </header>
          <TopNav />
          <main className="workspace" id="main-content" tabIndex={-1}>{children}</main>
        </section>
      </div>
    </>
  );
}
