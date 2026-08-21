import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarketBiasIndicator } from './MarketBiasIndicator';
import type { MarketBiasSummary } from '../domain/types';

const profile = {
  teamKey: 'home', teamName: 'Arsenal', venueContext: 'home' as const,
  direction: 'over' as const, strength: 'strong' as const, sampleSize: 10,
  nonPushSampleSize: 10, overCount: 7, underCount: 3, pushCount: 0,
  posteriorOverRate: 0.625, shrunkMeanResidual: 1.4, directionConfidence: 0.93,
  methodVersion: 'main_line_residual_v1',
};

describe('MarketBiasIndicator', () => {
  it('renders a one-profile rail with signed residual, sample and Swedish label', () => {
    render(<MarketBiasIndicator bias={{ scope: 'home', profiles: [profile] }} leagueBaseline={12.6} />);
    expect(screen.getByText('Mot Unibet-linan')).toBeInTheDocument();
    expect(screen.getByText('+1,4')).toBeInTheDocument();
    expect(screen.getByText('7/10')).toBeInTheDocument();
    expect(screen.getByLabelText(/Arsenal.*ÖVER.*7 av 10/i)).toHaveStyle({ '--bias-marker': '62.5%' });
  });

  it('orders total profiles home before away and renders insufficient explicitly', () => {
    const bias: MarketBiasSummary = {
      scope: 'total',
      profiles: [{ ...profile, venueContext: 'away', teamKey: 'away', teamName: 'Chelsea', direction: 'insufficient', strength: 'none', sampleSize: 3, nonPushSampleSize: 2, pushCount: 1 }, profile],
    };
    render(<MarketBiasIndicator bias={bias} leagueBaseline={null} />);
    expect(screen.getAllByRole('listitem').map((row) => row.getAttribute('data-team-key'))).toEqual(['home', 'away']);
    expect(screen.getByText('n < 6')).toBeInTheDocument();
    expect(screen.getByLabelText(/Chelsea.*otillräckligt/i)).toBeInTheDocument();
  });
});
