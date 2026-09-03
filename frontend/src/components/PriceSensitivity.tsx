import * as Dialog from '@radix-ui/react-dialog';
import { Calculator, X } from 'lucide-react';
import { useId, useState } from 'react';
import { formatExpectedRoi, formatProbability } from '../domain/formatters';
import { calculatePriceScenario, calculatePriceSensitivity } from '../domain/price-sensitivity';

interface PriceSensitivityProps {
  checkpointLabel: string;
  expectedRoiUnits: number | null;
  observationCount: number;
  predictedWinProbability: number | null;
  selectedOdds: number | null;
  selectionLabel: string;
}

function formatOdds(value: number): string {
  return value.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function parseDecimalOdds(value: string): number | null {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function priceStatus(expectedRoi: number): string {
  if (Math.abs(expectedRoi) < 0.000_001) return 'Vid modellens nollpris';
  return expectedRoi > 0 ? 'Över modellens nollpris' : 'Under modellens nollpris';
}

export function PriceSensitivity({
  checkpointLabel,
  expectedRoiUnits,
  observationCount,
  predictedWinProbability,
  selectedOdds,
  selectionLabel,
}: PriceSensitivityProps) {
  const sensitivity = calculatePriceSensitivity(predictedWinProbability, selectedOdds);
  const [draftOdds, setDraftOdds] = useState(selectedOdds?.toFixed(2) ?? '');
  const scenarioTitleId = useId();
  const scenarioHelpId = useId();

  if (!sensitivity) {
    return <strong>{expectedRoiUnits === null ? '—' : formatExpectedRoi(expectedRoiUnits)}</strong>;
  }

  const scenario = calculatePriceScenario(sensitivity.modelProbability, parseDecimalOdds(draftOdds));
  const triggerValue = expectedRoiUnits ?? sensitivity.current.modelExpectedRoi;

  return (
    <Dialog.Root
      onOpenChange={(open) => {
        if (open) setDraftOdds(sensitivity.current.decimalOdds.toFixed(2));
      }}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="price-sensitivity__trigger"
          aria-label={`Förklara pris och EV för ${selectionLabel}`}
        >
          <strong>{formatExpectedRoi(triggerValue)}</strong>
          <Calculator size={12} aria-hidden="true" />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="price-sensitivity__overlay" />
        <Dialog.Content className="price-sensitivity__dialog">
          <header className="price-sensitivity__header">
            <div>
              <span className="price-sensitivity__eyebrow">PRIS &amp; KÄNSLIGHET</span>
              <Dialog.Title>Vad kräver oddset?</Dialog.Title>
              <Dialog.Description>{selectionLabel}</Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button type="button" className="price-sensitivity__close" aria-label="Stäng pris och känslighet">
                <X size={18} aria-hidden="true" />
              </button>
            </Dialog.Close>
          </header>

          <section className="price-sensitivity__explanation" aria-label="Prisets utgångsläge">
            <p>
              Modellen satte sannolikheten till <strong>{formatProbability(sensitivity.modelProbability)}</strong>.
              Det motsvarar decimalodds <strong>{formatOdds(sensitivity.modelFairOdds)}</strong> där modellens EV är noll.
            </p>
            <div className="price-sensitivity__metrics">
              <div><span>Modell P</span><strong>{formatProbability(sensitivity.modelProbability)}</strong></div>
              <div><span>Modellens nollodds</span><strong>{formatOdds(sensitivity.modelFairOdds)}</strong></div>
              <div><span>Valt odds</span><strong>{formatOdds(sensitivity.current.decimalOdds)}</strong></div>
              <div><span>Break-even vid valt odds</span><strong>{formatProbability(sensitivity.current.marketBreakEvenProbability)}</strong></div>
            </div>
          </section>

          <section className="price-sensitivity__scenario" aria-labelledby={scenarioTitleId}>
            <div>
              <h3 id={scenarioTitleId}>Pröva ett annat odds</h3>
              <p>Se hur priset ändrar kalkylen medan modellens sannolikhet hålls fast.</p>
            </div>
            <label>
              <span>Decimalodds</span>
              <input
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={draftOdds}
                onChange={(event) => setDraftOdds(event.target.value)}
                aria-describedby={scenarioHelpId}
              />
            </label>
            <div id={scenarioHelpId} className="price-sensitivity__result" aria-live="polite">
              {scenario ? (
                <>
                  <div>
                    <span>Marknadens break-even</span>
                    <strong>{formatProbability(scenario.marketBreakEvenProbability)}</strong>
                  </div>
                  <div className={scenario.modelExpectedRoi >= 0 ? 'is-positive' : 'is-negative'}>
                    <span>Modellberäknad EV</span>
                    <strong>{formatExpectedRoi(scenario.modelExpectedRoi)}</strong>
                    <small>{priceStatus(scenario.modelExpectedRoi)}</small>
                  </div>
                </>
              ) : (
                <p className="price-sensitivity__error">Ange ett giltigt decimalodds över 1,00.</p>
              )}
            </div>
          </section>

          <footer className="price-sensitivity__footer">
            <p><strong>Formel:</strong> modell P × decimalodds − 1.</p>
            <p>{observationCount} observationer i gruppen · bästa checkpoint {checkpointLabel}.</p>
            <p>Detta är ett scenario från en fryst modellsannolikhet, inte bevisad träffsäkerhet, vinstlöfte eller insatsråd.</p>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
