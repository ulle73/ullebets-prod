import type { CSSProperties } from 'react';
import type { MarketBiasProfileSummary, MarketBiasSummary } from '../domain/types';

interface MarketBiasIndicatorProps {
  bias: MarketBiasSummary | null;
  leagueBaseline: number | null;
}

function markerPosition(profile: MarketBiasProfileSummary): string {
  if (profile.direction === 'insufficient') return '50%';
  return `${Math.max(5, Math.min(95, profile.posteriorOverRate * 100))}%`;
}

function signed(value: number): string {
  return value.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'always' });
}

function confidenceSegments(strength: MarketBiasProfileSummary['strength']): number {
  return strength === 'very_strong' ? 3 : strength === 'strong' ? 2 : strength === 'lean' ? 1 : 0;
}

function label(profile: MarketBiasProfileSummary): string {
  if (profile.direction === 'insufficient') return `${profile.teamName}: otillräckligt underlag, ${profile.sampleSize} matcher och ${profile.pushCount} pushar.`;
  const direction = profile.direction === 'over' ? 'ÖVER' : profile.direction === 'under' ? 'UNDER' : 'neutral';
  return `${profile.teamName}: ${direction} mot Unibet-linan, residual ${signed(profile.shrunkMeanResidual)}, ${profile.overCount} av ${profile.nonPushSampleSize} över och ${profile.pushCount} pushar.`;
}

function BiasRow({ profile }: { profile: MarketBiasProfileSummary }) {
  const insufficient = profile.direction === 'insufficient';
  const segments = confidenceSegments(profile.strength);
  const accessibleLabel = label(profile);
  return <li className={`market-bias__row market-bias__row--${profile.direction}`} data-team-key={profile.teamKey}>
    <div className="market-bias__meta"><strong title={profile.teamName}>{profile.teamName}</strong><span>{insufficient ? 'FÖR TUNT' : signed(profile.shrunkMeanResidual)}</span><span>{insufficient ? `n ${profile.sampleSize}` : `${profile.overCount}/${profile.nonPushSampleSize}`}</span><span className="market-bias__confidence" aria-label={`Styrka ${segments} av 3`} title={`Styrka ${segments} av 3`}>{[1, 2, 3].map((segment) => <i key={segment} className={segment <= segments ? 'is-active' : ''} />)}</span></div>
    <div className="market-bias__rail" style={{ '--bias-marker': markerPosition(profile) } as CSSProperties} aria-label={accessibleLabel} title={accessibleLabel}><span>UNDER</span><div className="market-bias__track"><i /><b className={insufficient ? 'is-hollow' : ''} /></div><span>ÖVER</span></div>
  </li>;
}

export function MarketBiasIndicator({ bias, leagueBaseline }: MarketBiasIndicatorProps) {
  const profiles = [...(bias?.profiles ?? [])].sort((left, right) => (left.venueContext === 'home' ? -1 : 1) - (right.venueContext === 'home' ? -1 : 1));
  return <section className="market-bias" aria-label="Mot Unibet-linan"><header><strong>Mot Unibet-linan</strong><span>Ligasnitt {leagueBaseline === null ? '—' : leagueBaseline.toLocaleString('sv-SE', { maximumFractionDigits: 2 })}</span></header>{profiles.length ? <ul>{profiles.map((profile) => <BiasRow key={profile.teamKey} profile={profile} />)}</ul> : <div className="market-bias__empty">—</div>}</section>;
}
