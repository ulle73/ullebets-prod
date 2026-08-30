import { ChevronDown } from 'lucide-react';
import type { MatchupEntry } from '../domain/types';
import { OddsMovement } from './OddsMovement';
import { VerdictIcon, type VerdictTone } from './VerdictIcon';

function formatNumber(value: number | null, digits = 1): string {
  return value === null ? '—' : value.toLocaleString('sv-SE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function predictorVisual(verdict: NonNullable<MatchupEntry['evaluation']>['predictor']['verdict'], status: string): { label: string; tone: VerdictTone } {
  if (verdict === 'hit') return { label: 'Prediktor: träff', tone: 'success' };
  if (verdict === 'miss') return { label: 'Prediktor: miss', tone: 'failure' };
  if (verdict === 'push') return { label: 'Prediktor: push', tone: 'push' };
  if (status === 'missing_actual') return { label: 'Prediktor: utfall saknas', tone: 'missing' };
  return { label: 'Prediktor: väntar', tone: 'pending' };
}

function marketVisual(verdict: NonNullable<MatchupEntry['evaluation']>['market']['verdict']): { label: string; tone: VerdictTone } {
  if (verdict === 'win') return { label: 'Marknad: vunnen', tone: 'success' };
  if (verdict === 'loss') return { label: 'Marknad: förlorad', tone: 'failure' };
  if (verdict === 'push') return { label: 'Marknad: push', tone: 'push' };
  return { label: 'Marknad: öppen', tone: 'pending' };
}

function marketCoverageReason(eligibility: string): string {
  if (eligibility === 'no_exact_market') return 'Exakt marknad saknas för stat, period, lagkontext och riktning';
  if (eligibility === 'missing_odds') return 'Exakt marknad hittades men odds saknas';
  if (eligibility === 'legacy_unknown') return 'Jämförbar historisk marknadsdata saknas';
  if (eligibility === 'not_selected') return 'Riktningen valdes inte av prediktorn';
  return 'Jämförbar spelmarknad saknas';
}

function signedNumber(value: number | null): string {
  if (value === null) return 'Saknas';
  return value.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'always' });
}

export function MatchupEvaluation({ signal }: { signal: MatchupEntry }) {
  const evaluation = signal.evaluation;
  if (!evaluation) return null;
  const { predictor, market, closing, provenance } = evaluation;
  if (predictor.verdict === null && ['open', 'not_selected'].includes(predictor.status)) return null;
  const predictorState = predictorVisual(predictor.verdict, predictor.status);
  const marketState = marketVisual(market.verdict);

  const compactResult = predictor.actualValue !== null && predictor.leagueBaseline !== null
    ? `${formatNumber(predictor.actualValue)} mot ${formatNumber(predictor.leagueBaseline)} · ${signedNumber(predictor.signedResidual)}`
    : predictor.status === 'missing_actual' ? 'Utfall saknas' : 'Väntar på resultat';

  return (
    <details className="matchup-evaluation">
      <summary>
        <span className="matchup-evaluation__summary-label">Prediktor & marknad</span>
        <span className="matchup-evaluation__summary-result"><VerdictIcon label={predictorState.label} tone={predictorState.tone} />{compactResult}</span>
        <ChevronDown size={15} aria-hidden="true" />
      </summary>
      <div className="matchup-evaluation__content" aria-label="Rättat matchup-utfall">
        <dl className="matchup-evaluation__predictor-details">
          <div><dt>Predictortröskel</dt><dd>{predictor.leagueBaseline === null ? 'Saknas' : formatNumber(predictor.leagueBaseline)}</dd></div>
          <div><dt>Faktiskt utfall</dt><dd>{predictor.actualValue === null ? 'Saknas' : formatNumber(predictor.actualValue)}</dd></div>
          <div><dt>Avstånd</dt><dd>{signedNumber(predictor.signedResidual)}</dd></div>
        </dl>
        {market.eligibility === 'eligible' ? (
          <div className={`matchup-evaluation__row matchup-evaluation__row--${market.verdict ?? 'pending'}`}>
            <strong>Spelmarknad <VerdictIcon label={marketState.label} tone={marketState.tone} /></strong>
            <span>{signal.condition} {formatNumber(market.line)} @ {market.selectedOdds === null ? 'odds saknas' : market.selectedOdds.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            <OddsMovement
              ariaLabel={`Visa oddsrörelse för ${signal.homeTeamName ?? 'hemmalag'} mot ${signal.awayTeamName ?? 'bortalag'}`}
              row={{
                direction: signal.condition.toLowerCase(),
                lineValue: market.line,
                selectedOdds: market.selectedOdds,
                closingOdds: closing.closingOdds,
                clvPct: closing.clvPct,
                beatClosingLine: closing.beatClosing,
                oddsHistory: closing.oddsHistory,
                homeTeamName: signal.homeTeamName,
                awayTeamName: signal.awayTeamName,
              }}
            />
          </div>
        ) : (
          <div className="matchup-evaluation__row matchup-evaluation__row--coverage"><VerdictIcon label="Marknad: saknas" tone="missing" /><strong>{marketCoverageReason(market.eligibility)}</strong><span>Ingår inte i ROI eller CLV</span></div>
        )}
        <small>{provenance.evidenceClass === 'legacy_descriptive' ? 'Historiskt · deskriptivt' : 'Forward T-1D'}</small>
      </div>
    </details>
  );
}
