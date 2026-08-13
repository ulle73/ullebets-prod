import { describe, expect, it } from 'vitest';
import {
  formatClosingQuality,
  formatClv,
  formatExpectedRoi,
  formatPeriod,
  formatProbability,
  formatScope,
  formatStat,
} from './formatters';

describe('frontend truth formatters', () => {
  it('formats grounded model probability and EV without inventing a generic score', () => {
    expect(formatProbability(0.614)).toBe('61,4 %');
    expect(formatExpectedRoi(0.112)).toBe('+11,2 %');
  });

  it('keeps missing CLV unavailable and distinguishes fallback from official closing', () => {
    expect(formatClv(null)).toBe('CLV saknas');
    expect(formatClv(5.5)).toBe('+5,5 %');
    expect(formatClosingQuality('t30_fallback')).toBe('T-30 fallback');
    expect(formatClosingQuality('t10')).toBe('Officiell T-10');
  });

  it('maps backend stat, period and scope keys deterministically', () => {
    expect(formatStat('cornerKicks')).toBe('Hörnor');
    expect(formatStat('shotsOnGoal')).toBe('Skott på mål');
    expect(formatPeriod('2ND')).toBe('2:a halvlek');
    expect(formatScope('away')).toBe('Bortalaget');
  });
});
