import { fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

describe('shell information architecture', () => {
  it('keeps four primary destinations inside the compact workspace header while exposing model and status as contextual tools', () => {
    const { container } = renderApp('/oversikt');
    const primary = screen.getByRole('navigation', { name: 'Huvudnavigation' });
    expect(within(primary).getAllByRole('link')).toHaveLength(4);
    expect(within(primary).queryByText(/Modell|Systemstatus/i)).not.toBeInTheDocument();
    const header = container.querySelector('.workspace-header');
    expect(header).not.toBeNull();
    expect(header).toContainElement(primary);
    const tools = screen.getByRole('navigation', { name: 'Verktyg' });
    expect(within(tools).getByRole('link', { name: 'Modell & proof' })).toHaveAttribute('href', '/modell');
    expect(within(tools).getByRole('link', { name: 'Systemstatus' })).toHaveAttribute('href', '/systemstatus');
  });

  it('opens the mobile match drawer on demand', async () => {
    renderApp('/oversikt');

    fireEvent.click(screen.getByRole('button', { name: 'Öppna matcher' }));

    expect(await screen.findByRole('dialog', { name: 'Dagens matcher' }, { timeout: 5_000 })).toBeInTheDocument();
  });
});
