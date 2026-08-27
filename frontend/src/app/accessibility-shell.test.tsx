import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

describe('shell information architecture', () => {
  it('keeps four primary destinations while exposing model and status as contextual tools', () => {
    renderApp('/oversikt');
    const primary = screen.getByRole('navigation', { name: 'Huvudnavigation' });
    expect(within(primary).getAllByRole('link')).toHaveLength(4);
    expect(within(primary).queryByText(/Modell|Systemstatus/i)).not.toBeInTheDocument();
    const tools = screen.getByRole('navigation', { name: 'Verktyg' });
    expect(within(tools).getByRole('link', { name: 'Modell & proof' })).toHaveAttribute('href', '/modell');
    expect(within(tools).getByRole('link', { name: 'Systemstatus' })).toHaveAttribute('href', '/systemstatus');
  });

  it('loads the mobile match drawer only when it is opened', async () => {
    renderApp('/oversikt');

    fireEvent.click(screen.getByRole('button', { name: 'Öppna matcher' }));

    expect(screen.getByText('Laddar matcherlista')).toBeInTheDocument();
    expect(await screen.findByRole('dialog', { name: 'Dagens matcher' }, { timeout: 5_000 })).toBeInTheDocument();
  });
});
