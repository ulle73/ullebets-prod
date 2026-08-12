import { CalendarDays, CheckCircle2, ChevronRight, CircleDot, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useAuto } from '../data/queries';
import { formatExpectedRoi, formatOdds, formatProbability } from '../domain/formatters';
import type { AutoSelection } from '../domain/types';

type FamilyFilter = 'v6' | 'legacy' | 'all';
type ResultFilter = 'all' | 'open' | 'win' | 'loss' | 'push' | 'excluded';

const STAT_LABELS: Record<string, string> = {
  cornerKicks: 'Hörnor',
  shotsOnGoal: 'Skott på mål',
  totalShots: 'Skott',
};

const SCOPE_LABELS: Record<string, string> = {
  home: 'HEMMA',
  away: 'BORTA',
  total: 'TOTAL',
};

const PERIOD_LABELS: Record<string, string> = {
  ALL: 'FT',
  '1ST': '1H',
  '2ND': '2H',
};

function selectionFamily(row: AutoSelection): Exclude<FamilyFilter, 'all'> {
  if (row.selectionFamily === 'v6') return 'v6';
  const provenance = `${row.modelId ?? ''} ${row.policyId ?? ''}`.toLowerCase();
  return provenance.includes('v6') ? 'v6' : 'legacy';
}

function resultBucket(row: AutoSelection): Exclude<ResultFilter, 'all'> {
  if (row.invalidForModel || row.validForForwardEvaluation === false || row.validForPerformance === false || row.resultStatus === 'excluded') return 'excluded';
  if (row.settlementResult === 'win') return 'win';
  if (row.settlementResult === 'loss') return 'loss';
  if (row.settlementResult === 'push') return 'push';
  return 'open';
}

function dateKey(iso: string | null): string {
  if (!iso) return 'missing-date';
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Stockholm',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(iso));
}

function dateHeading(iso: string | null): string {
  if (!iso) return 'DATUM SAKNAS';
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Stockholm',
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(new Date(iso)).toLocaleUpperCase('sv-SE');
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Stockholm',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso));
}

function formatShortDate(iso: string | null): string {
  if (!iso) return '—';
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Stockholm',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(iso));
}

function formatNumber(value: number | null, digits = 1): string {
  if (value === null) return '—';
  return value.toLocaleString('sv-SE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatPnl(value: number | null): string {
  if (value === null) return '—';
  const formatted = Math.abs(value).toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatted} u`;
}

function resultLabel(bucket: Exclude<ResultFilter, 'all'>): string {
  if (bucket === 'win') return 'VUNNEN';
  if (bucket === 'loss') return 'FÖRLORAD';
  if (bucket === 'push') return 'PUSH';
  if (bucket === 'excluded') return 'EXKLUDERAD';
  return 'ÖPPEN';
}

function resultDetail(row: AutoSelection): string | null {
  const bucket = resultBucket(row);
  if (!['win', 'loss', 'push'].includes(bucket)) return null;
  const actualDigits = row.actualValue !== null && Number.isInteger(row.actualValue) ? 0 : 1;
  return `Utfall ${formatNumber(row.actualValue, actualDigits)} · ${formatPnl(row.pnlUnits)}`;
}

export function AutoPage() {
  const [familyFilter, setFamilyFilter] = useState<FamilyFilter>('v6');
  const [statusFilter, setStatusFilter] = useState<ResultFilter>('all');
  const [leagueFilter, setLeagueFilter] = useState('all');
  const query = useAuto();
  if (query.isLoading) return <StateNotice state="loading" title="Läser Auto" detail="Hämtar registrerade forward_bets från V2." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Auto kunde inte läsas" detail="Ingen fallbacklista visas." />;

  const v6Count = query.data.selections.filter((row) => selectionFamily(row) === 'v6').length;
  const legacyCount = query.data.selections.length - v6Count;
  const familyRows = query.data.selections.filter((row) => familyFilter === 'all' || selectionFamily(row) === familyFilter);
  const leagues = [...new Set(familyRows.map((row) => row.leagueName).filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b, 'sv-SE'));
  const visibleRows = familyRows.filter((row) => {
    if (statusFilter !== 'all' && resultBucket(row) !== statusFilter) return false;
    return leagueFilter === 'all' || row.leagueName === leagueFilter;
  });
  const settledRows = familyRows.filter((row) => ['win', 'loss', 'push'].includes(resultBucket(row)));
  const openRows = familyRows.filter((row) => resultBucket(row) === 'open');
  const totalPnl = settledRows.reduce((sum, row) => sum + (row.pnlUnits ?? 0), 0);
  const totalStake = settledRows.reduce((sum, row) => sum + (row.stakeUnits ?? 1), 0);
  const roi = totalStake > 0 ? totalPnl / totalStake : null;
  const separatedRows = (query.data.excludedComboLegCount ?? 0) + (query.data.excludedShadowPredictionCount ?? 0);
  const groupedRows = visibleRows.reduce<Map<string, AutoSelection[]>>((groups, row) => {
    const key = dateKey(row.matchStartTime);
    const group = groups.get(key) ?? [];
    group.push(row);
    groups.set(key, group);
    return groups;
  }, new Map());

  return (
    <div className="page-stack auto-page">
      <PageHeader eyebrow="Auto · modelljournal" title="V6 Forward" subtitle="Frysta val före avspark. V6 och legacy hålls åtskilda i både urval och resultat." />

      <section className="auto-summary" aria-label="Forward-sammanfattning">
        <article className="auto-summary__card">
          <span className="auto-summary__icon"><CircleDot size={19} aria-hidden="true" /></span>
          <div><small>ÖPPNA VAL</small><strong>{openRows.length}</strong><p>väntar på rättning</p></div>
        </article>
        <article className="auto-summary__card">
          <span className="auto-summary__icon"><CheckCircle2 size={19} aria-hidden="true" /></span>
          <div><small>RÄTTADE</small><strong>{settledRows.length}</strong><p>{settledRows.filter((row) => resultBucket(row) === 'win').length} vunna · {settledRows.filter((row) => resultBucket(row) === 'loss').length} förlorade</p></div>
        </article>
        <article className="auto-summary__card auto-summary__card--roi">
          <span className="auto-summary__icon"><TrendingUp size={19} aria-hidden="true" /></span>
          <div><small>URVALS-ROI</small><strong>{roi === null ? '—' : formatExpectedRoi(roi)}</strong><p>{roi === null ? 'inga rättade val' : `${formatPnl(totalPnl)} · deskriptivt`}</p></div>
        </article>
      </section>

      <section className="auto-filters" aria-label="Filtrera forward-val">
        <div className="auto-filter-group">
          <span>VERSION</span>
          <div role="group" aria-label="Modellversion">
            <button type="button" className={familyFilter === 'v6' ? 'is-active' : ''} aria-pressed={familyFilter === 'v6'} onClick={() => { setFamilyFilter('v6'); setLeagueFilter('all'); }}>V6 <small>{v6Count}</small></button>
            <button type="button" className={familyFilter === 'legacy' ? 'is-active' : ''} aria-pressed={familyFilter === 'legacy'} onClick={() => { setFamilyFilter('legacy'); setLeagueFilter('all'); }}>Legacy <small>{legacyCount}</small></button>
            <button type="button" className={familyFilter === 'all' ? 'is-active' : ''} aria-pressed={familyFilter === 'all'} onClick={() => { setFamilyFilter('all'); setLeagueFilter('all'); }}>Alla <small>{query.data.selections.length}</small></button>
          </div>
        </div>
        <div className="auto-filter-group auto-filter-group--status">
          <span>STATUS</span>
          <div role="group" aria-label="Resultatstatus">
            {([
              ['all', 'Alla'],
              ['open', 'Öppna'],
              ['win', 'Vunna'],
              ['loss', 'Förlorade'],
              ['push', 'Push'],
              ['excluded', 'Exkluderade'],
            ] as const).map(([value, label]) => <button type="button" key={value} className={statusFilter === value ? 'is-active' : ''} aria-pressed={statusFilter === value} onClick={() => setStatusFilter(value)}>{label}</button>)}
          </div>
        </div>
        <label className="auto-league-filter">
          <span>LIGA</span>
          <select value={leagueFilter} onChange={(event) => setLeagueFilter(event.target.value)}>
            <option value="all">Alla ligor</option>
            {leagues.map((league) => <option value={league} key={league}>{league}</option>)}
          </select>
        </label>
      </section>

      {(separatedRows > 0 || query.data.collapsedDuplicateCount > 0) ? (
        <div className="auto-exposure-audit" role="status">
          <span><strong>{separatedRows}</strong> kombinations-/shadowrader separerade</span>
          <span><strong>{query.data.collapsedDuplicateCount}</strong> upprepade exponeringar sammanslagna</span>
          <span><strong>{query.data.count}</strong> faktiska raka forward-val</span>
        </div>
      ) : null}

      {query.data.selections.length === 0 ? <StateNotice state="empty" title="Inga registrerade forward-val" detail="V2 returnerade inga forward_bets. Frontend skapar inga egna kandidater." /> : visibleRows.length === 0 ? (
        <StateNotice state="empty" title={familyFilter === 'v6' ? 'Inga frysta V6-val ännu' : 'Inga val matchar filtret'} detail={familyFilter === 'v6' ? 'V6 väntar på ett kvalificerat val från en liga inom modellens träningsdomän. Legacy-data finns kvar under Legacy.' : 'Ändra version, status eller liga för att se andra rader.'} />
      ) : (
        <section className="auto-ledger" aria-label="Forward-val">
          {[...groupedRows.entries()].map(([key, rows]) => (
            <section className="auto-date-group" key={key}>
              <header className="auto-date-group__header"><CalendarDays size={14} aria-hidden="true" /><h2>{dateHeading(rows[0]?.matchStartTime ?? null)}</h2><span>{rows.length} val</span></header>
              <div className="auto-table" role="table" aria-label={`Forward-val ${dateHeading(rows[0]?.matchStartTime ?? null)}`}>
                <div className="auto-table__head" role="row">
                  {['TID', 'MATCH', 'STAT', 'SCOPE', 'PERIOD', 'RIKTNING', 'LINA', 'ODDS', 'MODELL P', 'EV', 'UTFALL'].map((label) => <span role="columnheader" key={label}>{label}</span>)}
                  <span aria-hidden="true" />
                </div>
                {rows.map((row, index) => {
                  const bucket = resultBucket(row);
                  const detail = resultDetail(row);
                  return (
                    <article className={`auto-table__row auto-table__row--${bucket}`} role="row" key={row.selectionKey ?? `${row.matchKey ?? 'selection'}:${index}`}>
                      <div className="auto-cell auto-cell--time" role="cell"><strong>{formatTime(row.matchStartTime)}</strong><small>{formatShortDate(row.matchStartTime)}</small></div>
                      <div className="auto-cell auto-cell--match" role="cell"><strong>{row.homeTeamName && row.awayTeamName ? `${row.homeTeamName} – ${row.awayTeamName}` : row.matchKey ?? 'Match saknas'}</strong><small>{row.leagueName ?? 'Liga saknas'}</small></div>
                      <div className="auto-cell auto-cell--stat" role="cell"><strong>{STAT_LABELS[row.statKey ?? ''] ?? row.statKey ?? 'Stat saknas'}</strong><small>{row.statKey ?? '—'}</small></div>
                      <div className="auto-cell" role="cell"><span className={`auto-dimension auto-dimension--${row.scope ?? 'unknown'}`}>{SCOPE_LABELS[row.scope ?? ''] ?? row.scope ?? '—'}</span></div>
                      <div className="auto-cell" role="cell"><span className="auto-dimension auto-dimension--period">{PERIOD_LABELS[row.period ?? ''] ?? row.period ?? '—'}</span></div>
                      <div className="auto-cell" role="cell"><strong className={`auto-direction auto-direction--${(row.direction ?? '').toLowerCase()}`}>{row.direction?.toLocaleUpperCase('sv-SE') ?? '—'}</strong></div>
                      <div className="auto-cell auto-cell--numeric" role="cell"><strong>{formatNumber(row.lineValue)}</strong></div>
                      <div className="auto-cell auto-cell--numeric" role="cell"><strong>{row.selectedOdds === null ? '—' : formatOdds(row.selectedOdds)}</strong></div>
                      <div className="auto-cell auto-cell--numeric auto-cell--model" role="cell"><strong>{row.predictedWinProbability === null ? '—' : formatProbability(row.predictedWinProbability)}</strong><small>{selectionFamily(row) === 'v6' ? 'V6 · PRIMÄR' : 'LEGACY'}</small></div>
                      <div className="auto-cell auto-cell--numeric auto-cell--ev" role="cell"><strong>{row.expectedRoiUnits === null ? '—' : formatExpectedRoi(row.expectedRoiUnits)}</strong></div>
                      <div className="auto-cell auto-cell--result" role="cell"><span className={`auto-result auto-result--${bucket}`}>{resultLabel(bucket)}</span>{detail ? <small>{detail}</small> : null}</div>
                      {row.matchKey ? <Link className="auto-row-link" to={`/matcher/${encodeURIComponent(row.matchKey)}`} aria-label={`Öppna ${row.homeTeamName ?? ''} mot ${row.awayTeamName ?? ''}`}><ChevronRight size={17} /></Link> : <span />}
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
        </section>
      )}
    </div>
  );
}
