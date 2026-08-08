import { ArrowDownRight, ArrowUpRight, Clock3, Database, ShieldAlert } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { Link } from 'react-router-dom';
import { formatExpectedRoi, formatOdds, formatPeriod, formatProbability, formatScope, formatStat } from '../domain/formatters';
import { signalCardHover } from '../domain/motion';
import type { Signal } from '../domain/types';
import { EvidenceBadge } from './EvidenceBadge';

interface SignalCardProps {
  signal: Signal;
  homeTeamName: string;
  awayTeamName: string;
}

export function SignalCard({ signal, homeTeamName, awayTeamName }: SignalCardProps) {
  const scopedTeam = signal.scope === 'home' ? homeTeamName : signal.scope === 'away' ? awayTeamName : 'Matchen';
  const DirectionIcon = signal.direction === 'OVER' ? ArrowUpRight : ArrowDownRight;
  const reducedMotion = useReducedMotion() ?? false;

  return (
    <motion.article
      className={`signal-card signal-card--${signal.direction.toLowerCase()}${signal.evidence === 'excluded' ? ' is-excluded' : ''}`}
      whileHover={signalCardHover(reducedMotion)}
      transition={reducedMotion ? { duration: 0 } : { duration: 0.16 }}
    >
      <header className="signal-card__header">
        <div className="signal-card__identity">
          <span className={`direction direction--${signal.direction.toLowerCase()}`}><DirectionIcon size={14} aria-hidden="true" />{signal.direction}</span>
          <EvidenceBadge evidence={signal.evidence} />
        </div>
        <Link to={`/matcher/${signal.matchKey}`} className="quiet-link">Matchdetalj</Link>
      </header>

      <div className="signal-card__bet">
        <p className="signal-card__market">{formatStat(signal.statKey)} · {formatPeriod(signal.period)}</p>
        <h3>{signal.direction === 'OVER' ? 'Över' : 'Under'} {signal.line.toLocaleString('sv-SE')}</h3>
        <p>{formatScope(signal.scope)} · {scopedTeam}</p>
      </div>

      <dl className="metric-grid">
        <div><dt>Modellsannolikhet</dt><dd>{formatProbability(signal.predictedWinProbability)}</dd></div>
        <div><dt>Modell-EV</dt><dd>{formatExpectedRoi(signal.expectedRoiUnits)}</dd></div>
        <div><dt>Odds</dt><dd>{formatOdds(signal.offeredOdds)}</dd></div>
      </dl>

      <footer className="signal-card__footer">
        <span><Database size={13} aria-hidden="true" />{signal.sourceProvider}</span>
        <span><Clock3 size={13} aria-hidden="true" />{signal.snapshotLabel}</span>
      </footer>

      {signal.evidence === 'excluded' ? (
        <div className="signal-card__warning"><ShieldAlert size={15} aria-hidden="true" /><span>{signal.evidenceReason}</span></div>
      ) : null}
    </motion.article>
  );
}
