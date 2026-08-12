import { Check, TriangleAlert } from 'lucide-react';
import type { CheckpointReadModel } from '../domain/types';

export function CheckpointTimeline({ checkpoints }: { checkpoints: CheckpointReadModel[] }) {
  return (
    <ol className="checkpoint-timeline" aria-label="Odds-checkpoints">
      {checkpoints.map((checkpoint) => {
        const Icon = checkpoint.invalidForModel ? TriangleAlert : Check;
        return (
          <li key={`${checkpoint.label}:${checkpoint.capturedAt ?? ''}`} className={`checkpoint checkpoint--${checkpoint.invalidForModel ? 'missing' : 'captured'}`}>
            <span className="checkpoint__icon"><Icon size={15} aria-hidden="true" /></span>
            <strong>{checkpoint.label}</strong>
            <span>{checkpoint.capturedAt ? new Date(checkpoint.capturedAt).toLocaleString('sv-SE') : 'Tid saknas'}</span>
          </li>
        );
      })}
    </ol>
  );
}
