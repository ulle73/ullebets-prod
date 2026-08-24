import type { FormulaEvidenceLevel, FormulaPerformanceMetrics } from '../domain/types';


function percentage(value: number | null, digits = 1): string {
  if (value === null) return '—';
  const prefix = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${prefix}${Math.abs(value).toLocaleString('sv-SE', { minimumFractionDigits: digits, maximumFractionDigits: digits })} %`;
}

function decimal(value: number | null, digits = 3): string {
  return value === null ? '—' : value.toLocaleString('sv-SE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function evidenceLabel(level: FormulaEvidenceLevel): string {
  if (level === 'comparable') return 'Jämförbart underlag';
  if (level === 'growing') return 'Växande underlag';
  return 'Tidigt underlag';
}

function tone(value: number | null): string {
  if (value === null || value === 0) return '';
  return value > 0 ? ' is-positive' : ' is-negative';
}

export function FormulaPerformanceTable({ groups }: { groups: FormulaPerformanceMetrics[] }) {
  return (
    <div className="formula-performance-table" role="table" aria-label="Jämförelse mellan formler och modeller">
      <div className="formula-performance-table__head" role="row">
        {['Formel', 'Underlag', 'ROI', 'CLV', 'Slår closing', 'Kalibrering'].map((label) => <span role="columnheader" key={label}>{label}</span>)}
      </div>
      {groups.map((group) => (
        <article className="formula-performance-table__row" role="row" key={group.formulaId ?? group.formulaLabel}>
          <div className="formula-performance-cell formula-performance-cell--identity" role="cell" data-label="Formel">
            <strong>{group.formulaLabel ?? group.formulaId ?? 'Okänd formel'}</strong>
            <small>{group.formulaId ?? 'ID saknas'} · {group.formulaFamily ?? 'familj saknas'}</small>
            <span className={`formula-evidence formula-evidence--${group.evidenceLevel}`}>{evidenceLabel(group.evidenceLevel)}</span>
          </div>
          <div className="formula-performance-cell" role="cell" data-label="Underlag">
            <strong>{group.settledBets} rättade spel</strong>
            <small>{group.uniqueSettledMatches} matcher</small>
            <small>{group.observations} scorer totalt</small>
          </div>
          <div className={`formula-performance-cell formula-performance-cell--metric${tone(group.roiPct)}`} role="cell" data-label="ROI">
            <strong>{percentage(group.roiPct)}</strong>
            <small>{group.pnlUnits > 0 ? '+' : ''}{group.pnlUnits.toLocaleString('sv-SE', { maximumFractionDigits: 2 })} u</small>
          </div>
          <div className={`formula-performance-cell formula-performance-cell--metric${tone(group.averageClvPct)}`} role="cell" data-label="CLV">
            <strong>{percentage(group.averageClvPct)}</strong>
            <small>{group.officialClvObservations} officiella</small>
          </div>
          <div className="formula-performance-cell formula-performance-cell--metric" role="cell" data-label="Slår closing">
            <strong>{percentage(group.clvBeatRatePct)}</strong>
            <small>{group.beatClosingLine}/{group.officialClvObservations} gånger</small>
          </div>
          <div className="formula-performance-cell formula-performance-cell--metric" role="cell" data-label="Kalibrering">
            <strong>{decimal(group.brierScore, 3)}</strong>
            <small>Brier · {group.calibrationObservations} utfall</small>
          </div>
        </article>
      ))}
    </div>
  );
}
