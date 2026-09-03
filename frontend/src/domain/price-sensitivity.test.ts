import { describe, expect, it } from 'vitest';
import { calculatePriceScenario, calculatePriceSensitivity } from './price-sensitivity';

describe('price sensitivity', () => {
  it('derives fair odds, market break-even and EV from the same frozen probability', () => {
    const result = calculatePriceSensitivity(0.61, 1.95);

    expect(result).not.toBeNull();
    expect(result?.modelFairOdds).toBeCloseTo(1 / 0.61, 10);
    expect(result?.current.marketBreakEvenProbability).toBeCloseTo(1 / 1.95, 10);
    expect(result?.current.modelExpectedRoi).toBeCloseTo(0.1895, 10);
  });

  it('shows that the same model probability becomes negative EV below its fair odds', () => {
    const scenario = calculatePriceScenario(0.61, 1.5);

    expect(scenario?.modelExpectedRoi).toBeCloseTo(-0.085, 10);
    expect(scenario?.marketBreakEvenProbability).toBeCloseTo(2 / 3, 10);
  });

  it.each([
    [null, 1.95],
    [0, 1.95],
    [1, 1.95],
    [Number.NaN, 1.95],
    [0.61, null],
    [0.61, 1],
    [0.61, Number.POSITIVE_INFINITY],
  ])('rejects invalid probability or odds (%s, %s)', (probability, odds) => {
    expect(calculatePriceScenario(probability, odds)).toBeNull();
  });
});
