import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

describe('shell information architecture', () => {
  it('keeps five primary destinations while exposing model and status as contextual tools', () => {
    renderApp('/oversikt');
    const primary = screen.getByRole('navigation', { name: 'Huvudnavigation' });
    expect(within(primary).getAllByRole('link')).toHaveLength(5);
    expect(within(primary).queryByText(/Modell|Systemstatus/i)).not.toBeInTheDocument();
    const tools = screen.getByRole('navigation', { name: 'Verktyg' });
    expect(within(tools).getByRole('link', { name: 'Modell & proof' })).toHaveAttribute('href', '/modell');
    expect(within(tools).getByRole('link', { name: 'Systemstatus' })).toHaveAttribute('href', '/systemstatus');
  });
});
