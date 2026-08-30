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

export function MatchupEvaluation({ signal }: { signal: MatchupEntry }) {
  const evaluation = signal.evaluation;
  if (!evaluation) return null;
  const { predictor, market, closing, provenance } = evaluation;
  if (predictor.verdict === null && ['open', 'not_selected'].includes(predictor.status)) return null;
  const predictorState = predictorVisual(predictor.verdict, predictor.status);
  const marketState = marketVisual(market.verdict);

  return (
    <section className="matchup-evaluation" aria-label="Rättat matchup-utfall">
      <div className={`matchup-evaluation__row matchup-evaluation__row--${predictor.verdict ?? 'pending'}`}>
        <strong>Prediktor <VerdictIcon label={predictorState.label} tone={predictorState.tone} /></strong>
        {predictor.actualValue !== null && predictor.leagueBaseline !== null ? (
          <span>Utfall {formatNumber(predictor.actualValue)} mot ligasnitt {formatNumber(predictor.leagueBaseline)} · {predictor.signedResidual !== null && predictor.signedResidual > 0 ? '+' : ''}{formatNumber(predictor.signedResidual)}</span>
        ) : <span>{predictor.status === 'missing_actual' ? 'Utfall saknas' : 'Väntar på resultat'}</span>}
      </div>
      {market.eligibility === 'eligible' ? (
        <div className={`matchup-evaluation__row matchup-evaluation__row--${market.verdict ?? 'pending'}`}>
          <strong>Marknad <VerdictIcon label={marketState.label} tone={marketState.tone} /></strong>
          <span>{signal.condition} {formatNumber(market.line)} @ {market.selectedOdds?.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
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
        <div className="matchup-evaluation__row matchup-evaluation__row--coverage"><strong>Ingen jämförbar spelmarknad</strong><span>Påverkar inte prediktorträffen</span></div>
      )}
      <small>{provenance.evidenceClass === 'legacy_descriptive' ? 'Historiskt · deskriptivt' : 'Forward T-1D'}</small>
    </section>
  );
}
