import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { App } from './App';

function renderRoute(route: string) {
  render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
}

describe('complete Style-1 route surface', () => {
  it('renders Auto as an evidence-safe forward-test surface', () => {
    renderRoute('/auto');
    expect(screen.getByRole('heading', { name: 'Auto' })).toBeInTheDocument();
    expect(screen.getByText(/0 spelbara V6-val/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Forward-test/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/bevisad vinst|proof-ready/i)).not.toBeInTheDocument();
  });

  it('renders Watchlist as local-only preference state', () => {
    renderRoute('/watchlist');
    expect(screen.getByRole('heading', { name: 'Watchlist' })).toBeInTheDocument();
    expect(screen.getAllByText(/bara identifierare/i).length).toBeGreaterThan(0);
  });

  it('renders Resultatloop from the saved operational snapshot without turning exclusions into losses', () => {
    renderRoute('/resultatloop');
    expect(screen.getByRole('heading', { name: 'Resultatloop' })).toBeInTheDocument();

    const settledLabel = screen.getByText('Giltigt avgjorda');
    const settledTile = settledLabel.closest('article');
    expect(settledTile).not.toBeNull();
    expect(within(settledTile!).getByText('64')).toBeInTheDocument();

    const excludedLabel = screen.getByText('Timing-exkluderade');
    const excludedTile = excludedLabel.closest('article');
    expect(excludedTile).not.toBeNull();
    expect(within(excludedTile!).getByText('3')).toBeInTheDocument();
  });

  it('renders Historik with descriptive Brazil evidence separated from V6 proof', () => {
    renderRoute('/historik');
    expect(screen.getByRole('heading', { name: 'Historik' })).toBeInTheDocument();
    expect(screen.getByText(/-23,40 %/i)).toBeInTheDocument();
    expect(screen.getAllByText(/OOD-diagnostik/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/inte V6-forward-proof/i).length).toBeGreaterThan(0);
  });

  it('renders the grounded A-League team-profile fixture without inventing league average', () => {
    renderRoute('/lag/adelaide-united');
    expect(screen.getByRole('heading', { name: 'Adelaide United' })).toBeInTheDocument();
    expect(screen.getAllByText('5,0').length).toBeGreaterThan(0);
    expect(screen.getByText(/Rank 1/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Verifierad testfixture/i).length).toBeGreaterThan(0);
  });

  it('renders model history and untouched forward evidence as separate states', () => {
    renderRoute('/modell');
    expect(screen.getByRole('heading', { name: 'Modell & proof' })).toBeInTheDocument();
    expect(screen.getByText(/Historisk backtest/i)).toBeInTheDocument();
    expect(screen.getByText('+28,65 %')).toBeInTheDocument();
    expect(screen.getByText(/0 in-domain/i)).toBeInTheDocument();
    expect(screen.getAllByText(/BLOCKED/i).length).toBeGreaterThan(0);
  });

  it('renders timestamped system evidence instead of presenting a stale snapshot as live', () => {
    renderRoute('/systemstatus');
    expect(screen.getByRole('heading', { name: 'Systemstatus' })).toBeInTheDocument();
    expect(screen.getByText(/Sparad verifieringssnapshot/i)).toBeInTheDocument();
    expect(screen.getByText(/T-3D/i)).toBeInTheDocument();
    expect(screen.getByText('678')).toBeInTheDocument();
    expect(screen.getAllByText(/T-10/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/UNPROVEN/i).length).toBeGreaterThan(0);
  });

  it('has no unfinished placeholder route copy left', () => {
    for (const route of ['/auto', '/watchlist', '/resultatloop', '/historik', '/lag/adelaide-united', '/modell', '/systemstatus']) {
      const view = render(
        <MemoryRouter initialEntries={[route]}>
          <App />
        </MemoryRouter>,
      );
      expect(view.queryByText(/byggs i nästa verifierade slice/i)).not.toBeInTheDocument();
      view.unmount();
    }
  });
});
