import type { EvidenceState } from '../domain/types';

const labels: Record<EvidenceState, string> = {
  analysis: 'Analys',
  'forward-test': 'Forward-test',
  historical: 'Historisk',
  excluded: 'Ej spelbar',
};

export function EvidenceBadge({ evidence }: { evidence: EvidenceState }) {
  return <span className={`evidence-badge evidence-badge--${evidence}`}>{labels[evidence]}</span>;
}
