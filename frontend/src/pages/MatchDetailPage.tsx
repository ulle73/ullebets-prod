import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { CheckpointTimeline } from '../components/CheckpointTimeline';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';
import { useMatchDetail } from '../data/queries';
import { formatClv, formatExpectedRoi, formatOdds, formatProbability } from '../domain/formatters';
import { FirstGoalPanel } from './match-detail/FirstGoalPanel';
import { MatchHeader } from './match-detail/MatchHeader';
import { ShotTempo } from './match-detail/ShotTempo';
import { StatComparison } from './match-detail/StatComparison';
import { TenMinuteChart } from './match-detail/TenMinuteChart';
import {
  buildFirstGoalView,
  buildShotTempoView,
  buildStatComparison,
  buildTenMinuteView,
  type MatchPeriod,
} from './match-detail/view-model';

type MatchTab = 'statistics' | 'odds' | 'backtest';

const TABS: Array<{ value: MatchTab; label: string }> = [
  { value: 'statistics', label: 'Statistik' },
  { value: 'odds', label: 'Lag & odds' },
  { value: 'backtest', label: 'Backtest' },
];

function abbreviation(name: string | null, fallback: string): string {
  return name?.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 3).toLocaleUpperCase('sv-SE') || fallback;
}

export function MatchDetailPage() {
  const { matchId } = useParams();
  const detail = useMatchDetail(matchId);
  const [period, setPeriod] = useState<MatchPeriod>('ALL');
  const [tab, setTab] = useState<MatchTab>('statistics');

  if (detail.isLoading) return <StateNotice state="loading" title="Läser match" detail="Hämtar kanonisk match och teamprofiles från V2." />;
  if (detail.isError || !detail.data) return <StateNotice state="failed" title="Matchen kunde inte läsas" detail="Ingen preview- eller fallbackmatch visas." />;

  const data = detail.data;
  const match = data.match;
  const teamProfiles = data.teamProfiles ?? { home: null, away: null };
  const analyticsData = data.teamProfiles ? data : { ...data, teamProfiles };
  const forwardSelections = data.forwardSelections ?? [];
  const forwardResults = data.forwardResults ?? [];
  const statRows = buildStatComparison(analyticsData, period);
  const homeShort = abbreviation(match.homeTeamName, 'HEM');
  const awayShort = abbreviation(match.awayTeamName, 'BOR');

  return (
    <article className="match-analytics-page">
      <nav className="match-tabs" role="tablist" aria-label="Matchdetaljer">
        {TABS.map((item) => (
          <button
            type="button"
            role="tab"
            aria-selected={tab === item.value}
            className={tab === item.value ? 'is-active' : ''}
            key={item.value}
            onClick={() => setTab(item.value)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <MatchHeader
        match={match}
        homeProfile={teamProfiles.home}
        awayProfile={teamProfiles.away}
        period={period}
        onPeriodChange={setPeriod}
      />

      {tab === 'statistics' ? (
        <div className="analytics-sections" role="tabpanel" aria-label="Statistik">
          {statRows.length ? <StatComparison rows={statRows} homeName={match.homeTeamName} awayName={match.awayTeamName} /> : <StateNotice state="empty" title="Statistik saknas för perioden" detail="Frontend fyller inte i saknade profilvärden." />}
          <ShotTempo states={buildShotTempoView(analyticsData)} homeLabel={homeShort} awayLabel={awayShort} />
          <TenMinuteChart view={buildTenMinuteView(analyticsData)} homeName={match.homeTeamName ?? homeShort} awayName={match.awayTeamName ?? awayShort} />
          <FirstGoalPanel view={buildFirstGoalView(analyticsData)} homeName={match.homeTeamName ?? homeShort} awayName={match.awayTeamName ?? awayShort} />
          <section className="analytics-panel analytics-panel--padded">
            <header className="analytics-section-title"><h2>Marknadsodds</h2><span>{data.marketOffers.length} linor</span></header>
            {data.marketOffers.length ? (
              <div className="analytics-market-table">
                <div className="analytics-market-row analytics-market-row--head"><span>MARKNAD</span><span>LINA</span><span>OVER</span><span>UNDER</span></div>
                {data.marketOffers.map((offer, index) => (
                  <div className="analytics-market-row" key={offer.offerKey ?? `${offer.statKey}:${offer.scope}:${offer.period}:${offer.line}:${index}`}>
                    <strong>{[offer.statKey, offer.scope, offer.period].filter(Boolean).join(' · ') || 'Marknad saknas'}</strong>
                    <span>{offer.line?.toLocaleString('sv-SE') ?? '—'}</span>
                    <span>{formatOdds(offer.overOdds)}</span>
                    <span>{formatOdds(offer.underOdds)}</span>
                  </div>
                ))}
              </div>
            ) : <StateNotice state="empty" title="Inga marknadsodds" detail="V2 returnerade inga normaliserade erbjudanden för matchen." />}
          </section>
          <section className="analytics-panel analytics-panel--padded">
            <header className="analytics-section-title"><h2>Utfall & forward-evidens</h2><span>{forwardSelections.length + forwardResults.length} rader</span></header>
            {forwardSelections.length || forwardResults.length ? (
              <div className="analytics-evidence-list">
                {forwardSelections.map((selection, index) => (
                  <article className="analytics-evidence-row" key={selection.selectionKey ?? selection.predictionKey ?? `selection:${index}`}>
                    <div><strong>{selection.direction?.toLocaleUpperCase('sv-SE') ?? '—'} {selection.statKey ?? 'Stat'} · {selection.scope ?? '—'} · {selection.period ?? '—'}</strong><small>Lina {selection.lineValue?.toLocaleString('sv-SE') ?? '—'} · odds {formatOdds(selection.selectedOdds)}</small></div>
                    <span>Modell P {formatProbability(selection.predictedWinProbability)}</span>
                    <span>EV {formatExpectedRoi(selection.expectedRoiUnits)}</span>
                  </article>
                ))}
                {forwardResults.map((result, index) => (
                  <article className="analytics-evidence-row analytics-evidence-row--settled" key={result.resultLoopKey ?? result.predictionKey ?? `result:${index}`}>
                    <div><strong>{result.settlementResult?.toLocaleUpperCase('sv-SE') ?? result.resultLoopStatus ?? 'RESULTAT'}</strong><small>Utfall {result.actualValue?.toLocaleString('sv-SE') ?? '—'} · PnL {result.pnlUnits === null ? '—' : `${result.pnlUnits > 0 ? '+' : ''}${result.pnlUnits.toLocaleString('sv-SE')} u`}</small></div>
                    <span>{result.officialClv ? `CLV ${formatClv(result.clvPct)}` : 'CLV saknas'}</span>
                    <span>{result.closingOdds === null ? 'Closing saknas' : `Close ${formatOdds(result.closingOdds)}`}</span>
                  </article>
                ))}
              </div>
            ) : <StateNotice state="empty" title="Ingen registrerad forward-evidens" detail="Matchup-ranking är analysdata och visas inte som ett registrerat spel." />}
          </section>
        </div>
      ) : null}

      {tab === 'odds' ? (
        <div className="analytics-sections" role="tabpanel" aria-label="Odds och EV">
          <section className="analytics-panel analytics-panel--padded">
            <header className="analytics-section-title"><h2>Checkpoint-tidslinje</h2></header>
            {data.checkpoints.length ? <CheckpointTimeline checkpoints={data.checkpoints} /> : <StateNotice state="empty" title="Inga checkpoints för matchen" detail="Frontend fyller inte i saknade snapshots." />}
          </section>
        </div>
      ) : null}

      {tab === 'backtest' ? (
        <div className="analytics-sections" role="tabpanel" aria-label="Backtest">
          <section className="analytics-panel analytics-panel--padded">
            <header className="analytics-section-title"><h2>Historiska matchups</h2></header>
            {data.matchups.length ? <div className="detail-signal-grid">{data.matchups.map((row) => <SignalCard key={row.entryKey} signal={row} />)}</div> : <StateNotice state="empty" title="Ingen matchup-ranking" detail="V2 returnerade inga historiska matchup-rader för matchen." />}
          </section>
        </div>
      ) : null}
    </article>
  );
}
