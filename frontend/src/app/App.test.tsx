import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { App } from './App';

describe('Ullebets application shell', () => {
  it('shows exactly the five approved primary destinations', () => {
    render(
      <MemoryRouter initialEntries={['/oversikt']}>
        <App />
      </MemoryRouter>,
    );

    const nav = screen.getByRole('navigation', { name: 'Huvudnavigation' });
    const links = Array.from(nav.querySelectorAll('a')).map((link) => link.textContent);
    expect(links).toEqual(['Översikt', 'Auto', 'Watchlist', 'Resultatloop', 'Historik']);
  });

  it('renders the overview decision surface without unsupported bookmaker or legacy generic score', () => {
    render(
      <MemoryRouter initialEntries={['/oversikt']}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Dagens matcher' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Bästa signaler' })).toBeInTheDocument();
    expect(screen.queryByText(/Bet365/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/85\.4|83\.5|72\.3/)).not.toBeInTheDocument();
  });
});
