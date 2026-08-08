import { describe, expect, it } from 'vitest';
import { previewMatchDetails, previewSignals } from './preview-data';

describe('preview data provenance', () => {
  it('does not attach unsourced probability, EV or odds values to the Brazil screenshot signals', () => {
    for (const signal of previewSignals) {
      expect(signal.evidence).toBe('excluded');
      expect(signal.predictedWinProbability).toBeNull();
      expect(signal.expectedRoiUnits).toBeNull();
      expect(signal.offeredOdds).toBeNull();
      expect(signal.sourceProvider).toBe('Unibet/Kambi');
    }
  });

  it('does not invent team-profile comparison values for Grêmio-São Paulo', () => {
    const detail = previewMatchDetails['gremio-sao-paulo'];
    expect(detail).toBeDefined();
    expect(detail?.teamStats).toEqual([]);
  });
});
