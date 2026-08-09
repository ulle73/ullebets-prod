import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { CheckpointTimeline } from '../components/CheckpointTimeline';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';
import { useMatchDetail } from '../data/queries';
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
  const statRows = buildStatComparison(data, period);
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
        homeProfile={data.teamProfiles.home}
        awayProfile={data.teamProfiles.away}
        period={period}
        onPeriodChange={setPeriod}
      />

      {tab === 'statistics' ? (
        <div className="analytics-sections" role="tabpanel" aria-label="Statistik">
          {statRows.length ? <StatComparison rows={statRows} homeName={match.homeTeamName} awayName={match.awayTeamName} /> : <StateNotice state="empty" title="Statistik saknas för perioden" detail="Frontend fyller inte i saknade profilvärden." />}
          <ShotTempo states={buildShotTempoView(data)} homeLabel={homeShort} awayLabel={awayShort} />
          <TenMinuteChart view={buildTenMinuteView(data)} homeName={match.homeTeamName ?? homeShort} awayName={match.awayTeamName ?? awayShort} />
          <FirstGoalPanel view={buildFirstGoalView(data)} homeName={match.homeTeamName ?? homeShort} awayName={match.awayTeamName ?? awayShort} />
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
