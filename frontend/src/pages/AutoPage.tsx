import { CalendarDays, CheckCircle2, ChevronRight, CircleDot, Target, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { matchDetailPath } from '../domain/match-route';
import { OddsMovement } from '../components/OddsMovement';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { WorkflowFilters, type WorkflowFilter } from '../components/WorkflowFilters';
import { useAuto } from '../data/queries';
import { autoQueryFromSearch, patchSearchParams } from '../data/workflow-query';
import { formatExpectedRoi, formatProbability } from '../domain/formatters';
import type { AutoSelection } from '../domain/types';
import { CHECKPOINT_OPTIONS, DIRECTION_OPTIONS, PERIOD_OPTIONS, SCOPE_OPTIONS, STAT_OPTIONS } from '../domain/workflow-filter-options';

type FamilyFilter = 'v6' | 'legacy' | 'all';
type ResultFilter = 'all' | 'open' | 'settled' | 'win' | 'loss' | 'push' | 'excluded';

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

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('sv-SE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatPnl(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const formatted = Math.abs(value).toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatted} u`;
}

function checkpointLabel(value: string | null | undefined): string {
  return value?.replace('T_MINUS_', 'T-').replace(/M$/, '').replace(/H$/, 'H').replace(/D$/, 'D') ?? 'saknas';
}

function observationCount(row: AutoSelection): number {
  return row.observationCount ?? 1;
}

function resultLabel(bucket: Exclude<ResultFilter, 'all'>): string {
  if (bucket === 'win') return 'VUNNEN';
  if (bucket === 'loss') return 'FÖRLORAD';
  if (bucket === 'push') return 'PUSH';
  if (bucket === 'excluded') return 'EXKLUDERAD';
  return 'ÖPPEN';
}

function statusFilterFromQuery(value: string | undefined): ResultFilter {
  return ['open', 'settled', 'win', 'loss', 'push', 'excluded'].includes(value ?? '') ? value as ResultFilter : 'all';
}

function matchesResultFilter(row: AutoSelection, filter: ResultFilter): boolean {
  if (filter === 'all') return true;
  const bucket = resultBucket(row);
  if (filter === 'settled') return ['win', 'loss', 'push'].includes(bucket);
  return bucket === filter;
}

function formatClv(value: number | null | undefined, signed = true): string {
  if (value === null || value === undefined) return '—';
  const formatted = Math.abs(value).toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (!signed) return `${formatted} %`;
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatted} %`;
}

function acceptedClv(row: AutoSelection): boolean {
  return row.acceptedClv ?? row.officialClv ?? (row.acceptedClvCount ?? 0) > 0;
}

function clvDetail(row: AutoSelection): string {
  if (!acceptedClv(row) || row.clvPct === null || row.clvPct === undefined) return 'Closing saknas';
  const distance = row.clvDistancePct ?? Math.abs(row.clvPct);
  const result = row.clvPct > 0 ? 'Slog close' : row.clvPct < 0 ? 'Missade close' : 'Matchade close';
  return `${result} med ${formatClv(distance, false)} · ${checkpointLabel(row.closingCheckpoint)}`;
}

function resultDetail(row: AutoSelection): string | null {
  const bucket = resultBucket(row);
  if (!['win', 'loss', 'push'].includes(bucket)) return null;
  const actualDigits = row.actualValue !== null && Number.isInteger(row.actualValue) ? 0 : 1;
  return `Utfall ${formatNumber(row.actualValue, actualDigits)} · ${formatPnl(row.pnlUnits)}`;
}

export function AutoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [familyFilter, setFamilyFilter] = useState<FamilyFilter>('v6');
  const [leagueFilter, setLeagueFilter] = useState('all');
  const serverQuery = autoQueryFromSearch(searchParams);
  const statusFilter = statusFilterFromQuery(serverQuery.status);
  const pageLimit = serverQuery.limit ?? 50;
  const pageOffset = serverQuery.offset ?? 0;
  const query = useAuto(serverQuery);
  if (query.isLoading) return <StateNotice state="loading" title="Läser spel & resultat" detail="Hämtar registrerade spel, rättning och CLV från V2." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Spel & resultat kunde inte läsas" detail="Ingen fallbacklista visas." />;

  const pageV6Count = query.data.selections.filter((row) => selectionFamily(row) === 'v6').length;
  const pageLegacyCount = query.data.selections.length - pageV6Count;
  const v6Count = query.data.summary.byFamily?.v6?.groups ?? pageV6Count;
  const legacyCount = query.data.summary.byFamily?.legacy?.groups ?? pageLegacyCount;
  const allCount = query.data.summary.groups ?? query.data.selections.length;
  const familyRows = query.data.selections.filter((row) => familyFilter === 'all' || selectionFamily(row) === familyFilter);
  const familySummary = familyFilter === 'all'
    ? query.data.summary
    : query.data.summary.byFamily?.[familyFilter];
  const leagues = [...new Set(familyRows.map((row) => row.leagueName).filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b, 'sv-SE'));
  const visibleRows = familyRows.filter((row) => {
    if (!matchesResultFilter(row, statusFilter)) return false;
    return leagueFilter === 'all' || row.leagueName === leagueFilter;
  });
  const settledRows = familyRows.filter((row) => ['win', 'loss', 'push'].includes(resultBucket(row)));
  const openRows = familyRows.filter((row) => resultBucket(row) === 'open');
  const localTotalPnl = settledRows.reduce((sum, row) => sum + (row.pnlUnits ?? 0), 0);
  const localTotalStake = settledRows.reduce((sum, row) => sum + (row.stakeUnits ?? 1), 0);
  const totalPnl = familySummary?.pnlUnits ?? localTotalPnl;
  const roi = familySummary?.roiPct !== null && familySummary?.roiPct !== undefined
    ? familySummary.roiPct / 100
    : localTotalStake > 0 ? localTotalPnl / localTotalStake : null;
  const openObservationCount = familySummary?.open ?? openRows.reduce((sum, row) => sum + observationCount(row), 0);
  const openGroupCount = familySummary?.openGroups ?? openRows.length;
  const settledObservationCount = familySummary?.settled ?? settledRows.reduce((sum, row) => sum + observationCount(row), 0);
  const wonObservationCount = familySummary?.wins ?? settledRows.filter((row) => resultBucket(row) === 'win').reduce((sum, row) => sum + observationCount(row), 0);
  const lostObservationCount = familySummary?.losses ?? settledRows.filter((row) => resultBucket(row) === 'loss').reduce((sum, row) => sum + observationCount(row), 0);
  const separatedRows = (query.data.excludedComboLegCount ?? 0) + (query.data.excludedShadowPredictionCount ?? 0);
  const acceptedRows = familyRows.filter(acceptedClv);
  const acceptedClvCount = familySummary?.acceptedClvCount
    ?? acceptedRows.reduce((sum, row) => sum + (row.acceptedClvCount ?? 1), 0);
  const beatClosingLineCount = familySummary?.beatClosingLineCount
    ?? acceptedRows.reduce((sum, row) => sum + (row.beatClosingLineCount ?? (row.beatClosingLine ? 1 : 0)), 0);
  const t30ClvCount = familySummary?.t30ClvCount
    ?? acceptedRows.reduce((sum, row) => sum + (row.t30ClvCount ?? (row.closingQuality === 't30_fallback' ? 1 : 0)), 0);
  const t10ClvCount = familySummary?.t10ClvCount
    ?? acceptedRows.reduce((sum, row) => sum + (row.t10ClvCount ?? (row.closingQuality === 't10' ? 1 : 0)), 0);
  const averageAcceptedClvPct = familySummary?.averageAcceptedClvPct
    ?? (acceptedRows.length > 0
      ? acceptedRows.reduce((sum, row) => sum + (row.averageClvPct ?? row.clvPct ?? 0), 0) / acceptedRows.length
      : null);
  const groupedRows = visibleRows.reduce<Map<string, AutoSelection[]>>((groups, row) => {
    const key = dateKey(row.matchStartTime);
    const group = groups.get(key) ?? [];
    group.push(row);
    groups.set(key, group);
    return groups;
  }, new Map());
  const workflowFilters: WorkflowFilter[] = [
    { key: 'stat', label: 'Stat', value: serverQuery.stat ?? '', options: STAT_OPTIONS },
    { key: 'scope', label: 'Lag/scope', value: serverQuery.scope ?? '', options: SCOPE_OPTIONS },
    { key: 'period', label: 'Period', value: serverQuery.period ?? '', options: PERIOD_OPTIONS },
    { key: 'direction', label: 'Riktning', value: serverQuery.direction ?? '', options: DIRECTION_OPTIONS },
    { key: 'checkpoint', label: 'Checkpoint', value: serverQuery.checkpoint ?? '', options: CHECKPOINT_OPTIONS },
  ];
  const changeWorkflowFilter = (key: string, value: string) => setSearchParams(patchSearchParams(searchParams, { [key]: value }, { resetOffset: true }));
  const changeStatusFilter = (value: ResultFilter) => setSearchParams(patchSearchParams(searchParams, { status: value === 'all' ? undefined : value }, { resetOffset: true }));
  const changePageLimit = (value: number) => setSearchParams(patchSearchParams(searchParams, { limit: value }, { resetOffset: true }));

  return (
    <div className="page-stack auto-page">
      <PageHeader eyebrow="V6 Forward · speljournal" title="Spel & resultat" subtitle="Frysta spel, rättning, ROI och CLV mot accepterad T-30/T-10-closing på samma yta." />
      <h2 className="auto-page__model-title">V6 Forward</h2>

      <section className="auto-summary" aria-label="Spel- och resultatsammanfattning">
        <article className="auto-summary__card">
          <span className="auto-summary__icon"><CircleDot size={19} aria-hidden="true" /></span>
          <div><small>ÖPPNA SPEL</small><strong>{openObservationCount}</strong><p>{openGroupCount} grupper väntar på rättning</p></div>
        </article>
        <article className="auto-summary__card">
          <span className="auto-summary__icon"><CheckCircle2 size={19} aria-hidden="true" /></span>
          <div><small>RÄTTADE SPEL</small><strong>{settledObservationCount}</strong><p>{wonObservationCount} vunna · {lostObservationCount} förlorade</p></div>
        </article>
        <article className="auto-summary__card auto-summary__card--roi">
          <span className="auto-summary__icon"><TrendingUp size={19} aria-hidden="true" /></span>
          <div><small>URVALS-ROI</small><strong>{roi === null ? '—' : formatExpectedRoi(roi)}</strong><p>{roi === null ? 'inga rättade val' : `${formatPnl(totalPnl)} · deskriptivt`}</p></div>
        </article>
        <article className="auto-summary__card auto-summary__card--clv">
          <span className="auto-summary__icon"><Target size={19} aria-hidden="true" /></span>
          <div><small>CLV MOT CLOSE</small><strong>{formatClv(averageAcceptedClvPct)}</strong><p>{acceptedClvCount === 0 ? 'väntar på T-30/T-10-closing' : `${beatClosingLineCount}/${acceptedClvCount} slog close · ${t30ClvCount} T-30 · ${t10ClvCount} T-10`}</p></div>
        </article>
      </section>

      <WorkflowFilters filters={workflowFilters} pageLimit={pageLimit} onFilterChange={changeWorkflowFilter} onPageLimitChange={changePageLimit} />

      <section className="auto-filters" aria-label="Filtrera forward-val">
        <div className="auto-filter-group">
          <span>VERSION</span>
          <div role="group" aria-label="Modellversion">
            <button type="button" className={familyFilter === 'v6' ? 'is-active' : ''} aria-pressed={familyFilter === 'v6'} onClick={() => { setFamilyFilter('v6'); setLeagueFilter('all'); }}>V6 <small>{v6Count}</small></button>
            <button type="button" className={familyFilter === 'legacy' ? 'is-active' : ''} aria-pressed={familyFilter === 'legacy'} onClick={() => { setFamilyFilter('legacy'); setLeagueFilter('all'); }}>Legacy <small>{legacyCount}</small></button>
            <button type="button" className={familyFilter === 'all' ? 'is-active' : ''} aria-pressed={familyFilter === 'all'} onClick={() => { setFamilyFilter('all'); setLeagueFilter('all'); }}>Alla <small>{allCount}</small></button>
          </div>
        </div>
        <div className="auto-filter-group auto-filter-group--status">
          <span>STATUS</span>
          <div role="group" aria-label="Resultatstatus">
            {([
              ['all', 'Alla'],
              ['open', 'Öppna'],
              ['settled', 'Rättade'],
              ['win', 'Vunna'],
              ['loss', 'Förlorade'],
              ['push', 'Push'],
              ['excluded', 'Exkluderade'],
            ] as const).map(([value, label]) => <button type="button" key={value} className={statusFilter === value ? 'is-active' : ''} aria-pressed={statusFilter === value} onClick={() => changeStatusFilter(value)}>{label}</button>)}
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
          <span><strong>{query.data.observationCount ?? query.data.summary.total}</strong> faktiska 1u-observationer i <strong>{query.data.count}</strong> grupper</span>
        </div>
      ) : null}

      {query.data.selections.length === 0 ? <StateNotice state="empty" title="Inga registrerade forward-val" detail="V2 returnerade inga forward_bets. Frontend skapar inga egna kandidater." /> : visibleRows.length === 0 ? (
        <StateNotice state="empty" title={familyFilter === 'v6' ? 'Inga frysta V6-val ännu' : 'Inga val matchar filtret'} detail={familyFilter === 'v6' ? 'V6 väntar på ett kvalificerat val från en liga inom modellens träningsdomän. Legacy-data finns kvar under Legacy.' : 'Ändra version, status eller liga för att se andra rader.'} />
      ) : (
        <section className="auto-ledger" aria-label="Spel & resultat">
          {[...groupedRows.entries()].map(([key, rows]) => (
            <section className="auto-date-group" key={key}>
              <header className="auto-date-group__header"><CalendarDays size={14} aria-hidden="true" /><h2>{dateHeading(rows[0]?.matchStartTime ?? null)}</h2><span>{rows.reduce((sum, row) => sum + observationCount(row), 0)} spel · {rows.length} grupper</span></header>
              <div className="auto-table" role="table" aria-label={`Forward-val ${dateHeading(rows[0]?.matchStartTime ?? null)}`}>
                <div className="auto-table__head" role="row">
                  {['TID', 'MATCH', 'STAT', 'SCOPE', 'PERIOD', 'RIKTNING', 'LINA', 'ODDS', 'MODELL P', 'EV', 'CLV', 'UTFALL'].map((label) => <span role="columnheader" key={label}>{label}</span>)}
                  <span aria-hidden="true" />
                </div>
                {rows.map((row, index) => {
                  const bucket = resultBucket(row);
                  const detail = resultDetail(row);
                  return (
                    <article className={`auto-table__row auto-table__row--${bucket}`} role="row" key={row.selectionKey ?? `${row.matchKey ?? 'selection'}:${index}`}>
                      <div className="auto-cell auto-cell--time" role="cell"><strong>{formatTime(row.matchStartTime)}</strong><small>{formatShortDate(row.matchStartTime)}</small></div>
                      <div className="auto-cell auto-cell--match" role="cell">
                        <strong>
                          {row.homeTeamName && row.awayTeamName ? <>
                            {row.homeTeamKey ? <Link to={`/lag/${encodeURIComponent(row.homeTeamKey)}`}>{row.homeTeamName}</Link> : row.homeTeamName}
                            <span> – </span>
                            {row.awayTeamKey ? <Link to={`/lag/${encodeURIComponent(row.awayTeamKey)}`}>{row.awayTeamName}</Link> : row.awayTeamName}
                          </> : row.matchKey ?? 'Match saknas'}
                        </strong>
                        <small>{row.leagueKey ? <Link to={`/liga/${encodeURIComponent(row.leagueKey)}`}>{row.leagueName ?? 'Liga saknas'}</Link> : row.leagueName ?? 'Liga saknas'}</small>
                      </div>
                      <div className="auto-cell auto-cell--stat" role="cell"><strong>{STAT_LABELS[row.statKey ?? ''] ?? row.statKey ?? 'Stat saknas'}</strong><small>{row.statKey ?? '—'}</small></div>
                      <div className="auto-cell" role="cell"><span className={`auto-dimension auto-dimension--${row.scope ?? 'unknown'}`}>{SCOPE_LABELS[row.scope ?? ''] ?? row.scope ?? '—'}</span></div>
                      <div className="auto-cell" role="cell"><span className="auto-dimension auto-dimension--period">{PERIOD_LABELS[row.period ?? ''] ?? row.period ?? '—'}</span></div>
                      <div className="auto-cell" role="cell"><strong className={`auto-direction auto-direction--${(row.direction ?? '').toLowerCase()}`}>{row.direction?.toLocaleUpperCase('sv-SE') ?? '—'}</strong></div>
                      <div className="auto-cell auto-cell--numeric" role="cell"><strong>{formatNumber(row.lineValue)}</strong></div>
                      <div className="auto-cell auto-cell--numeric auto-cell--odds" role="cell"><OddsMovement row={row} /></div>
                      <div className="auto-cell auto-cell--numeric auto-cell--model" role="cell"><strong>{row.predictedWinProbability === null ? '—' : formatProbability(row.predictedWinProbability)}</strong><small>{selectionFamily(row) === 'v6' ? 'V6 · PRIMÄR' : 'LEGACY'}</small></div>
                      <div className="auto-cell auto-cell--numeric auto-cell--ev" role="cell"><strong>{row.expectedRoiUnits === null ? '—' : formatExpectedRoi(row.expectedRoiUnits)}</strong><small>{observationCount(row)} obs · bäst {checkpointLabel(row.bestSnapshotLabel ?? row.snapshotLabel)}</small></div>
                      <div className={`auto-cell auto-cell--numeric auto-cell--clv${acceptedClv(row) ? row.clvPct !== null && row.clvPct !== undefined && row.clvPct >= 0 ? ' is-positive' : ' is-negative' : ''}`} role="cell"><strong>{acceptedClv(row) ? formatClv(row.clvPct) : '—'}</strong><small>{clvDetail(row)}</small></div>
                      <div className="auto-cell auto-cell--result" role="cell"><span className={`auto-result auto-result--${bucket}`}>{resultLabel(bucket)}</span>{detail ? <small>{detail}</small> : null}</div>
                      {row.matchKey ? <Link className="auto-row-link" to={matchDetailPath(row.matchKey)} aria-label={`Öppna ${row.homeTeamName ?? ''} mot ${row.awayTeamName ?? ''}`}><ChevronRight size={17} /></Link> : <span />}
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
        </section>
      )}
      <nav className="workflow-pagination" aria-label="Sidindelning Spel & resultat">
        <button
          type="button"
          onClick={() => setSearchParams(patchSearchParams(searchParams, { offset: Math.max(0, pageOffset - pageLimit) }))}
          disabled={pageOffset === 0}
        >
          Föregående sida
        </button>
        <span>Rad {pageOffset + 1}–{pageOffset + query.data.selections.length}</span>
        <button
          type="button"
          onClick={() => setSearchParams(patchSearchParams(searchParams, { offset: pageOffset + pageLimit }))}
          disabled={!query.data.page.hasMore}
        >
          Nästa sida
        </button>
      </nav>
    </div>
  );
}
