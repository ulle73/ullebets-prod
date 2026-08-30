import { CircleAlert, CircleCheck, CircleMinus, CircleX, Clock3 } from 'lucide-react';

export type VerdictTone = 'success' | 'failure' | 'push' | 'pending' | 'missing';

const icons = {
  success: CircleCheck,
  failure: CircleX,
  push: CircleMinus,
  pending: Clock3,
  missing: CircleAlert,
};

export function VerdictIcon({ label, tone }: { label: string; tone: VerdictTone }) {
  const Icon = icons[tone];
  return (
    <span className={`verdict-icon verdict-icon--${tone}`} role="img" aria-label={label} title={label}>
      <Icon size={16} strokeWidth={2.4} aria-hidden="true" />
    </span>
  );
}
