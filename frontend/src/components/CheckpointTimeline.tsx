import { Check, Clock, Minus, TriangleAlert } from 'lucide-react';
import type { Checkpoint } from '../domain/types';

const stateLabels: Record<Checkpoint['state'], string> = {
  captured: 'Fångad',
  'not-yet': 'Inte aktuell ännu',
  fallback: 'Fallback',
  missing: 'Saknas',
};

export function CheckpointTimeline({ checkpoints }: { checkpoints: Checkpoint[] }) {
  return (
    <ol className="checkpoint-timeline" aria-label="Odds-checkpoints">
      {checkpoints.map((checkpoint) => {
        const Icon = checkpoint.state === 'captured' ? Check : checkpoint.state === 'missing' ? TriangleAlert : checkpoint.state === 'fallback' ? Clock : Minus;
        return (
          <li key={checkpoint.label} className={`checkpoint checkpoint--${checkpoint.state}`}>
            <span className="checkpoint__icon"><Icon size={15} aria-hidden="true" /></span>
            <strong>{checkpoint.label}</strong>
            <span>{stateLabels[checkpoint.state]}</span>
          </li>
        );
      })}
    </ol>
  );
}
