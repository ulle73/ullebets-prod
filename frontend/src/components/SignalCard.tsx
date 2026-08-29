import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { signalCardHover } from '../domain/motion';
import type { MatchupEntry } from '../domain/types';
import { EntityLink } from './EntityLink';
import { MarketBiasIndicator } from './MarketBiasIndicator';
import { MatchupEvaluation } from './MatchupEvaluation';

interface SignalCardProps {
  signal: MatchupEntry;
}

function scopeLabel(scope: MatchupEntry['scope']): string {
  if (scope === 'home') return 'Hemmalaget';
  if (scope === 'away') return 'Bortalaget';
  return 'Totalt';
}

export function SignalCard({ signal }: SignalCardProps) {
  const isOver = signal.condition === 'OVER';
  const DirectionIcon = isOver ? ArrowUpRight : ArrowDownRight;
  const reducedMotion = useReducedMotion() ?? false;

  return (
    <motion.article
      className={`signal-card signal-card--${signal.condition.toLowerCase()}`}
      whileHover={signalCardHover(reducedMotion)}
      transition={reducedMotion ? { duration: 0 } : { duration: 0.16 }}
    >
      <header className="signal-card__header">
        <div>
          <EntityLink kind="league" id={signal.leagueKey} className="signal-card__league">
            {signal.leagueName ?? 'Liga saknas'}
          </EntityLink>
          <strong className="signal-card__match">
            <EntityLink kind="team" id={signal.homeTeamKey}>{signal.homeTeamName ?? 'Okänt lag'}</EntityLink>
            <span aria-hidden="true"> vs </span>
            <EntityLink kind="team" id={signal.awayTeamKey}>{signal.awayTeamName ?? 'Okänt lag'}</EntityLink>
          </strong>
        </div>
        <div className="matchup-score" aria-label="Matchup-score">
          <span>Score</span>
          <strong>{signal.score === null ? '—' : signal.score.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</strong>
        </div>
      </header>

      <div className="matchup-tags">
        <span className={`direction direction--${signal.condition.toLowerCase()}`}><DirectionIcon size={13} aria-hidden="true" />{signal.condition}</span>
        <span>{signal.statLabel ?? signal.statKey ?? 'Stat saknas'}</span>
        <span>{scopeLabel(signal.scope)}</span>
        <span>{signal.periodLabel ?? signal.period ?? 'Period saknas'}</span>
        {signal.rankingWindowMatches !== null ? (
          <span title="Ranking bygger pa lagens senaste matcher">Form {signal.rankingWindowMatches}</span>
        ) : null}
      </div>

      <MarketBiasIndicator bias={signal.marketBias} leagueBaseline={signal.leagueBaseline} />

      <MatchupEvaluation signal={signal} />

      <footer className="signal-card__footer">
        {signal.rankPosition !== null ? <span>Rank #{signal.rankPosition}</span> : null}
        <EntityLink kind="match" id={signal.matchKey} className="quiet-link" ariaLabel="Matchdetalj">Matchdetalj</EntityLink>
      </footer>
    </motion.article>
  );
}
