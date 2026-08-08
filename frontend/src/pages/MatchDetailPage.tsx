import { ArrowLeft, Clock3, DatabaseZap } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { CheckpointTimeline } from '../components/CheckpointTimeline';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';
import { previewMatchDetails } from '../data/preview-data';
import { formatKickoff } from '../domain/formatters';

export function MatchDetailPage() {
  const { matchId } = useParams();
  const detail = matchId ? previewMatchDetails[matchId] : undefined;

  if (!detail) {
    return <StateNotice state="empty" title="Matchen finns inte i förhandsdatan" detail="När read-API:t kopplas in används den kanoniska matchnyckeln här." />;
  }

  return (
    <div className="page-stack">
      <Link to="/oversikt" className="back-link"><ArrowLeft size={15} />Till översikt</Link>
      <section className="match-hero">
        <div className="match-hero__meta"><span>{detail.match.leagueName}</span><span><Clock3 size={14} />{formatKickoff(detail.match.startTime)}</span><span><DatabaseZap size={14} />{detail.freshnessLabel}</span></div>
        <div className="team-versus">
          <div className="team-block"><span className="team-monogram">GR</span><strong>{detail.match.homeTeamName}</strong></div>
          <span className="versus-badge">VS</span>
          <div className="team-block team-block--right"><span className="team-monogram">SP</span><strong>{detail.match.awayTeamName}</strong></div>
        </div>
      </section>

      <StateNotice state={detail.dataState} title="Utanför V6-domän" detail="Modellrader får granskas diagnostiskt men får inte rankas som Auto-val eller användas som forward-proof." />

      <section className="content-section">
        <div className="section-heading"><div><p className="eyebrow">Oddsflöde</p><h2>Checkpoint-tidslinje</h2></div><span className="muted-label">T-30/T-10 saknas i denna preview</span></div>
        <CheckpointTimeline checkpoints={detail.checkpoints} />
      </section>

      <section className="content-section">
        <div className="section-heading"><div><p className="eyebrow">Analys</p><h2>Signaler</h2></div><span className="muted-label">Unibet/Kambi</span></div>
        <div className="detail-signal-grid">{detail.signals.map((signal) => <SignalCard key={signal.id} signal={signal} homeTeamName={detail.match.homeTeamName} awayTeamName={detail.match.awayTeamName} />)}</div>
      </section>

      <section className="content-section">
        <div className="section-heading"><div><p className="eyebrow">Teamprofiles</p><h2>Lagjämförelse</h2></div><Link className="quiet-link" to="/lag/gremio">Öppna lagprofil</Link></div>
        <div className="stats-table" role="table" aria-label="Lagstatistik">
          <div className="stats-row stats-row--head" role="row"><span>Stat</span><span>{detail.match.homeTeamName}</span><span>{detail.match.awayTeamName}</span><span>Ligasnitt</span></div>
          {detail.teamStats.map((row) => <div className="stats-row" role="row" key={row.label}><strong>{row.label}</strong><span>{row.homeValue?.toLocaleString('sv-SE') ?? 'Saknas'}</span><span>{row.awayValue?.toLocaleString('sv-SE') ?? 'Saknas'}</span><span>{row.leagueAverage?.toLocaleString('sv-SE') ?? 'Saknas'}</span></div>)}
        </div>
      </section>
    </div>
  );
}
