export interface PriceScenario {
  decimalOdds: number;
  marketBreakEvenProbability: number;
  modelExpectedRoi: number;
}

export interface PriceSensitivity {
  modelProbability: number;
  modelFairOdds: number;
  current: PriceScenario;
}

export function calculatePriceScenario(
  modelProbability: number | null | undefined,
  decimalOdds: number | null | undefined,
): PriceScenario | null {
  if (
    modelProbability === null
    || modelProbability === undefined
    || decimalOdds === null
    || decimalOdds === undefined
    || !Number.isFinite(modelProbability)
    || !Number.isFinite(decimalOdds)
    || modelProbability <= 0
    || modelProbability >= 1
    || decimalOdds <= 1
  ) {
    return null;
  }

  return {
    decimalOdds,
    marketBreakEvenProbability: 1 / decimalOdds,
    modelExpectedRoi: modelProbability * decimalOdds - 1,
  };
}

export function calculatePriceSensitivity(
  modelProbability: number | null | undefined,
  selectedOdds: number | null | undefined,
): PriceSensitivity | null {
  const current = calculatePriceScenario(modelProbability, selectedOdds);
  if (!current || modelProbability === null || modelProbability === undefined) return null;

  return {
    modelProbability,
    modelFairOdds: 1 / modelProbability,
    current,
  };
}
