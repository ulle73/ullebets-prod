import { ArrowLeft, Clock3 } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { MatchSummary, TeamProfileSummary } from '../../domain/types';
import type { MatchPeriod } from './view-model';

function initials(name: string | null): string {
  if (!name) return '—';
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toLocaleUpperCase('sv-SE') ?? '').join('');
}

function kickoff(iso: string | null): string | null {
  if (!iso) return null;
  return new Intl.DateTimeFormat('sv-SE', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Stockholm',
  }).format(new Date(iso));
}

function TeamIdentity({
  name,
  teamKey,
  imageUrl,
  profile,
  side,
}: {
  name: string | null;
  teamKey: string | null;
  imageUrl: string | null | undefined;
  profile: TeamProfileSummary | null;
  side: 'home' | 'away';
}) {
  const content = (
    <>
      <span className="match-team__crest">
        <span aria-hidden="true">{initials(name)}</span>
        {imageUrl ? <img src={imageUrl} alt={name ?? 'Lag'} onError={(event) => { event.currentTarget.hidden = true; }} /> : null}
      </span>
      <span className="match-team__copy">
        <strong>{name ?? 'Okänt lag'}</strong>
        <small>{profile ? `${profile.sampleSize} matcher` : 'Profil saknas'}</small>
      </span>
    </>
  );
  return teamKey ? <Link className={`match-team match-team--${side}`} to={`/lag/${encodeURIComponent(teamKey)}`}>{content}</Link> : <div className={`match-team match-team--${side}`}>{content}</div>;
}

const PERIODS: Array<{ value: MatchPeriod; label: string; short: string }> = [
  { value: 'ALL', label: 'Hela matchen', short: 'FT' },
  { value: '1ST', label: 'Första halvlek', short: '1H' },
  { value: '2ND', label: 'Andra halvlek', short: '2H' },
];

export function MatchHeader({
  match,
  homeProfile,
  awayProfile,
  period,
  onPeriodChange,
}: {
  match: MatchSummary;
  homeProfile: TeamProfileSummary | null;
  awayProfile: TeamProfileSummary | null;
  period: MatchPeriod;
  onPeriodChange: (period: MatchPeriod) => void;
}) {
  return (
    <header className="analytics-match-header">
      <Link to="/oversikt" className="analytics-back" aria-label="Till översikt"><ArrowLeft size={18} /></Link>
      <h1 className="sr-only">{match.homeTeamName} mot {match.awayTeamName}</h1>
      <div className="analytics-match-header__teams">
        <TeamIdentity name={match.homeTeamName} teamKey={match.homeTeamKey} imageUrl={match.homeTeamImageUrl} profile={homeProfile} side="home" />
        <div className="analytics-match-header__center">
          <span className="analytics-league">{match.leagueName ?? 'Liga saknas'}</span>
          <strong className="analytics-score">{match.homeScore !== null && match.awayScore !== null ? `${match.homeScore}–${match.awayScore}` : 'VS'}</strong>
          {kickoff(match.startTime) ? <span className="analytics-kickoff"><Clock3 size={13} />{kickoff(match.startTime)}</span> : null}
        </div>
        <TeamIdentity name={match.awayTeamName} teamKey={match.awayTeamKey} imageUrl={match.awayTeamImageUrl} profile={awayProfile} side="away" />
      </div>
      <div className="analytics-periods" aria-label="Matchperiod">
        {PERIODS.map((item) => (
          <button
            type="button"
            key={item.value}
            className={period === item.value ? 'is-active' : ''}
            aria-pressed={period === item.value}
            aria-label={item.label}
            onClick={() => onPeriodChange(item.value)}
          >
            <span className="analytics-periods__long">{item.label}</span>
            <span className="analytics-periods__short">{item.short}</span>
          </button>
        ))}
      </div>
    </header>
  );
}
