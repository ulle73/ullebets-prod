import type { MatchupEntry } from '../domain/types';
import { OddsMovement } from './OddsMovement';

function formatNumber(value: number | null, digits = 1): string {
  return value === null ? '—' : value.toLocaleString('sv-SE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function predictorLabel(verdict: NonNullable<MatchupEntry['evaluation']>['predictor']['verdict']): string {
  if (verdict === 'hit') return 'TRÄFF';
  if (verdict === 'miss') return 'MISS';
  if (verdict === 'push') return 'PUSH';
  return 'VÄNTAR';
}

function marketLabel(verdict: NonNullable<MatchupEntry['evaluation']>['market']['verdict']): string {
  if (verdict === 'win') return 'VUNNEN';
  if (verdict === 'loss') return 'FÖRLORAD';
  if (verdict === 'push') return 'PUSH';
  return 'ÖPPEN';
}

export function MatchupEvaluation({ signal }: { signal: MatchupEntry }) {
  const evaluation = signal.evaluation;
  if (!evaluation) return null;
  const { predictor, market, closing, provenance } = evaluation;
  if (predictor.verdict === null && ['open', 'not_selected'].includes(predictor.status)) return null;

  return (
    <section className="matchup-evaluation" aria-label="Rättat matchup-utfall">
      <div className={`matchup-evaluation__row matchup-evaluation__row--${predictor.verdict ?? 'pending'}`}>
        <strong>Prediktor: {predictorLabel(predictor.verdict)}</strong>
        {predictor.actualValue !== null && predictor.leagueBaseline !== null ? (
          <span>Utfall {formatNumber(predictor.actualValue)} mot ligasnitt {formatNumber(predictor.leagueBaseline)} · {predictor.signedResidual !== null && predictor.signedResidual > 0 ? '+' : ''}{formatNumber(predictor.signedResidual)}</span>
        ) : <span>{predictor.status === 'missing_actual' ? 'Utfall saknas' : 'Väntar på resultat'}</span>}
      </div>
      {market.eligibility === 'eligible' ? (
        <div className={`matchup-evaluation__row matchup-evaluation__row--${market.verdict ?? 'pending'}`}>
          <strong>Marknad: {marketLabel(market.verdict)}</strong>
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
