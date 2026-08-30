import { Activity, BarChart3, CalendarDays, ChevronDown, Crosshair, SlidersHorizontal, Target } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SignalCard } from '../components/SignalCard';
import { StateNotice } from '../components/StateNotice';
import { VerdictIcon } from '../components/VerdictIcon';
import { useDashboard, useMatchupEvaluation } from '../data/queries';

function formatPct(value: number | null): string {
  return value === null ? 'Saknas' : `${value.toLocaleString('sv-SE', { maximumFractionDigits: 1 })} %`;
}

function formatSigned(value: number | null, suffix = ''): string {
  return value === null ? 'Saknas' : `${value.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'always' })}${suffix}`;
}

function resolvedLabel(count: number): string {
  return `${count} ${count === 1 ? 'rättad' : 'rättade'}`;
}

export function OverviewPage() {
  const [searchParams] = useSearchParams();
  const requestedDate = searchParams.get('date') || undefined;
  const dashboard = useDashboard(requestedDate);
  const evaluation = useMatchupEvaluation(
    requestedDate ? { dateFrom: requestedDate, dateTo: requestedDate } : {},
    Boolean(requestedDate),
  );
  const [league, setLeague] = useState('all');
  const [stat, setStat] = useState('all');

  const matchups = useMemo(() => dashboard.data?.matchups ?? [], [dashboard.data?.matchups]);
  const leagues = useMemo(() => Array.from(new Set(matchups.map((row) => row.leagueName).filter((value): value is string => Boolean(value)))).sort(), [matchups]);
  const stats = useMemo(() => Array.from(new Map(matchups.filter((row) => row.statKey).map((row) => [row.statKey!, row.statLabel ?? row.statKey!])).entries()).sort((a, b) => a[1].localeCompare(b[1], 'sv')), [matchups]);
  const filtered = matchups.filter((row) => (league === 'all' || row.leagueName === league) && (stat === 'all' || row.statKey === stat));
  const over = filtered.filter((row) => row.condition === 'OVER');
  const under = filtered.filter((row) => row.condition === 'UNDER');

  if (dashboard.isLoading) {
    return <StateNotice state="loading" title="Hämtar dagens matcher" detail="Matchlistan och matchup-rankingen uppdateras." />;
  }
  if (dashboard.isError) {
    return <StateNotice state="failed" title="Dagens matcher kunde inte hämtas" detail="Försök igen om en stund. Ingen reservdata visas när källan inte kan nås." />;
  }
  if (!dashboard.data) {
    return <StateNotice state="empty" title="Ingen matchdata tillgänglig" detail="Det finns ingen läsbar data för den aktuella vyn." />;
  }

  const data = dashboard.data;
  const sourceLabel = data.matchupSource === 'computed_read_only'
    ? 'Aktuell matchup-ranking'
    : data.matchupSource === 'persisted'
      ? 'Matchup-ranking'
      : 'Ranking saknas';

  return (
    <div className="page-stack">
      <section className="page-hero">
        <div>
          <p className="eyebrow">Översikt</p>
          <h2>Dagens matchups</h2>
          <p className="page-subtitle">Jämför dagens högst rankade OVER- och UNDER-matchups per stat, period och lagkontext.</p>
        </div>
        <div className="summary-strip" aria-label="Översiktsstatus">
          <span><CalendarDays size={14} />{data.selectedDate}</span>
          <span><Activity size={14} />{data.matches.length} matcher</span>
          <span>{sourceLabel}</span>
        </div>
      </section>

      {data.matches.length === 0 ? (
        <StateNotice state="empty" title="Inga matcher för valt datum" detail="Välj ett annat datum för att se tillgängliga matcher." />
      ) : null}
      {data.matches.length > 0 && matchups.length === 0 ? (
        <StateNotice state="empty" title="Matchup-ranking saknas" detail="Matcher finns för dagen, men det finns ännu inte tillräcklig data för en matchup-ranking." />
      ) : null}

      {evaluation.data ? (
        <div className="matchup-results-overview">
          <div className="matchup-summary-panels">
            <section className="matchup-summary-panel" aria-label="Prediktorresultat">
              <header><span className="matchup-summary-panel__icon"><Target size={17} aria-hidden="true" /></span><div><h3>Prediktor</h3><p>Rättad mot fryst ligabaseline</p></div></header>
              <div className="matchup-summary-panel__metrics">
                <article><span>Rättade</span><strong>{evaluation.data.predictor.resolved}</strong><small>av {evaluation.data.predictor.contexts} kontexter</small></article>
                <article><span>Träffsäkerhet</span><strong>{formatPct(evaluation.data.predictor.nonPushHitRatePct)}</strong><small className="matchup-verdict-counts"><span><VerdictIcon label="Antal predictorträffar" tone="success" />{evaluation.data.predictor.hits}</span><span><VerdictIcon label="Antal predictormissar" tone="failure" />{evaluation.data.predictor.misses}</span>{evaluation.data.predictor.pushes ? <span><VerdictIcon label="Antal predictorpushar" tone="push" />{evaluation.data.predictor.pushes}</span> : null}</small></article>
                <article><span>Medianavstånd</span><strong>{formatSigned(evaluation.data.predictor.medianSignedResidual)}</strong><small>utfall minus tröskel i vald riktning</small></article>
                <article><span>Mot bästa konstanta riktning</span><strong>{formatSigned(evaluation.data.predictor.constantDirectionBaseline.liftPctPoints, ' pp')}</strong><small>{evaluation.data.predictor.constantDirectionBaseline.bestDirection === 'tie' ? 'OVER och UNDER lika' : evaluation.data.predictor.constantDirectionBaseline.bestDirection ? `Alltid ${evaluation.data.predictor.constantDirectionBaseline.bestDirection.toUpperCase()}` : 'För tunt underlag'}</small></article>
              </div>
            </section>

            <section className="matchup-summary-panel" aria-label="Resultat för spelbara marknader">
              <header><span className="matchup-summary-panel__icon"><Crosshair size={17} aria-hidden="true" /></span><div><h3>Spelbara marknader</h3><p>Separat från predictorträffen</p></div></header>
              <div className="matchup-summary-panel__metrics">
                <article><span>Jämförbara</span><strong>{evaluation.data.market.eligible}</strong><small>{evaluation.data.coverage.marketEligiblePct === null ? 'Täckning saknas' : `${formatPct(evaluation.data.coverage.marketEligiblePct)} av kontexterna`}</small></article>
                <article><span>Rättade</span><strong>{evaluation.data.market.resolved}</strong><small>ROI-nämnare</small></article>
                <article><span>ROI</span><strong>{formatPct(evaluation.data.market.roiPct)}</strong><small>{evaluation.data.market.resolved ? `${evaluation.data.market.pnlUnits.toLocaleString('sv-SE', { maximumFractionDigits: 2, signDisplay: 'always' })} u` : 'Inga rättade marknader'}</small></article>
                <article><span>CLV</span><strong>{formatPct(evaluation.data.market.meanClvPct)}</strong><small>Closing {evaluation.data.market.closingCovered} av {evaluation.data.market.resolved}</small><small>Slog closing {evaluation.data.market.beatClosing} av {evaluation.data.market.closingCovered}</small></article>
              </div>
            </section>
          </div>

          <details className="matchup-diagnostics">
            <summary><span><BarChart3 size={15} aria-hidden="true" />Rankingpoängens träffsäkerhet</span><ChevronDown size={15} aria-hidden="true" /></summary>
            <div className="matchup-diagnostics__content">
              <p>Poängen är en sorteringspoäng, inte en sannolikhet. Träffprocenten exkluderar push och varje intervall visar sitt eget underlag.</p>
              <div className="matchup-score-buckets">
                {evaluation.data.predictor.scoreBuckets.map((bucket) => (
                  <article key={bucket.key}>
                    <span>{bucket.label}</span>
                    <strong>{formatPct(bucket.nonPushHitRatePct)}</strong>
                    <small>{resolvedLabel(bucket.resolved)}</small>
                    <small>Medianavstånd {formatSigned(bucket.medianSignedResidual)}</small>
                  </article>
                ))}
              </div>
            </div>
          </details>
        </div>
      ) : null}

      <details className="matchup-filter-panel">
        <summary><span><SlidersHorizontal size={15} aria-hidden="true" />Filter</span><ChevronDown size={15} aria-hidden="true" /></summary>
        <div className="filter-toolbar">
          <select aria-label="Liga" value={league} onChange={(event) => setLeague(event.target.value)}>
            <option value="all">Alla ligor</option>
            {leagues.map((value) => <option value={value} key={value}>{value}</option>)}
          </select>
          <select aria-label="Stat" value={stat} onChange={(event) => setStat(event.target.value)}>
            <option value="all">Alla statstyper</option>
            {stats.map(([key, label]) => <option value={key} key={key}>{label}</option>)}
          </select>
        </div>
      </details>

      <div className="signal-columns">
        <section className="signal-column">
          <header className="signal-column__header"><span className="signal-column__dot signal-column__dot--over" /><h3>Över – topp 20</h3><span>{over.length}</span></header>
          <div className="signal-list">{over.map((row) => <SignalCard key={row.entryKey} signal={row} rankTotal={over.length} />)}</div>
        </section>
        <section className="signal-column">
          <header className="signal-column__header"><span className="signal-column__dot signal-column__dot--under" /><h3>Under – topp 20</h3><span>{under.length}</span></header>
          <div className="signal-list">{under.map((row) => <SignalCard key={row.entryKey} signal={row} rankTotal={under.length} />)}</div>
        </section>
      </div>
    </div>
  );
}
