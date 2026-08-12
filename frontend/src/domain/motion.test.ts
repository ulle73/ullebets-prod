import { describe, expect, it } from 'vitest';
import { signalCardHover } from './motion';

describe('motion accessibility', () => {
  it('removes transform hover motion when reduced motion is requested', () => {
    expect(signalCardHover(true)).toEqual({});
    expect(signalCardHover(false)).toEqual({ y: -2 });
  });
});
