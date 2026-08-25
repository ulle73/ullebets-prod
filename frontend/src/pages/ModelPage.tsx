import { Activity, BrainCircuit, GitBranch, Scale, ShieldCheck, Target, TrendingUp } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { FormulaPerformanceFilters } from '../components/FormulaPerformanceFilters';
import { FormulaPerformanceTable } from '../components/FormulaPerformanceTable';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { PaginationBar } from '../components/PaginationBar';
import { StateNotice } from '../components/StateNotice';
import { formulaPerformanceQueryFromSearch } from '../data/formula-performance-query';
import { useFormulaPerformance, useModel } from '../data/queries';
import { patchSearchParams } from '../data/workflow-query';
import type { FormulaPerformanceQuery } from '../data/api';
import type { ModelResponse } from '../domain/types';


function humanizeStatus(value: string): string {
  const normalized = value.trim().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').toLocaleLowerCase('sv-SE');
  return normalized ? `${normalized[0]?.toLocaleUpperCase('sv-SE') ?? ''}${normalized.slice(1)}` : 'Okänd status';
}

function percentage(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const prefix = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${prefix}${Math.abs(value).toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

function units(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  const prefix = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${prefix}${Math.abs(value).toLocaleString('sv-SE', { maximumFractionDigits: 2 })} u`;
}

function RuntimeProof({ data }: { data: ModelResponse }) {
  const modelStatuses = data.modelStatuses ?? [];
  const policyStatuses = data.policyStatuses ?? [];
  return (
    <section className="runtime-proof" aria-labelledby="runtime-proof-title">
      <div className="section-heading">
        <div><p className="eyebrow">Registrerad produktion</p><h2 id="runtime-proof-title">Modell & proof</h2></div>
      </div>
      <p className="proof-caveat">Det här är driftstatus för de riktiga förregistrerade valen. Den hålls separat från den breda skuggjämförelsen ovan. Antal observationer är inte proof. Positiv forward-ROI eller CLV måste verifieras separat innan det får behandlas som evidens för framtida beslut.</p>
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Modellscorer" value={data.scoreCount} detail="Registrerade scorer" icon={<Activity size={14} />} />
        <MetricTile label="Forward-val" value={data.forwardSelectionCount} detail="Förregistrerade observationer" tone="brand" icon={<GitBranch size={14} />} />
        <MetricTile label="Avgjorda forward" value={data.settledForwardCount} detail="Giltiga för utvärdering" />
        <MetricTile label="Officiell closing" value={data.officialClvCount} detail="T-10-mätningar" tone="good" icon={<ShieldCheck size={14} />} />
      </div>
      <div className="evidence-lanes">
        <article>
          <span className="evidence-lane__label">Modellstatus</span>
          {modelStatuses.length ? <div className="league-chip-grid">{modelStatuses.map((status) => <span className="status-badge status-badge--unproven" key={status}>{humanizeStatus(status)}</span>)}</div> : <p>Ingen registrerad modellstatus finns i läsvyn.</p>}
        </article>
        <article>
          <span className="evidence-lane__label evidence-lane__label--forward">Policystatus</span>
          {policyStatuses.length ? <div className="league-chip-grid">{policyStatuses.map((status) => <span className="status-badge status-badge--partial" key={status}>{humanizeStatus(status)}</span>)}</div> : <p>Ingen registrerad policystatus finns i läsvyn.</p>}
        </article>
      </div>
      <div className="runtime-proof__identities">
        <article>
          <span>Modeller</span>
          {data.modelIds.length ? <div className="league-chip-grid">{data.modelIds.map((id) => <span key={id}>{id}</span>)}</div> : <p>Inga modell-ID registrerade.</p>}
        </article>
        <article>
          <span>Policy-ID</span>
          {data.policyIds.length ? <div className="league-chip-grid">{data.policyIds.map((id) => <span key={id}>{id}</span>)}</div> : <p>Inga policy-ID registrerade.</p>}
        </article>
      </div>
    </section>
  );
}

export function ModelPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const readQuery = formulaPerformanceQueryFromSearch(searchParams);
  const performance = useFormulaPerformance(readQuery);
  const model = useModel();
  const limit = readQuery.limit ?? 50;
  const offset = readQuery.offset ?? 0;
  const changeFilter = (key: keyof FormulaPerformanceQuery, value: string) => {
    setSearchParams(patchSearchParams(searchParams, { [key]: value }, { resetOffset: true }));
  };

  return (
    <div className="page-stack formula-performance-page">
      <PageHeader
        eyebrow="Alla aktiva formler · immutable forward-journal"
        title="Modelljämförelse"
        subtitle="Varje giltig +EV-signal räknas som ett virtuellt 1u-spel vid exakt den tidpunkt oddset hämtades. Filtrera för att se var modellerna faktiskt fungerar bäst."
      />

      {performance.isLoading ? (
        <StateNotice state="loading" title="Läser modelljämförelsen" detail="Summerar skuggspel, rättning och closing utan att blanda in Auto-valen." />
      ) : performance.isError || !performance.data ? (
        <StateNotice state="failed" title="Modelljämförelsen kunde inte läsas" detail="Ingen lokal beräkning eller reserv-ROI visas när journal-API:t saknas." />
      ) : (
        <>
          <section className="formula-performance-summary" aria-label="Sammanfattning av formeljämförelsen">
            <MetricTile label="Virtuella +EV-spel" value={performance.data.summary.shadowBets} detail={`${performance.data.summary.observations} scorer · ${performance.data.summary.uniqueMatches} matcher`} tone="brand" icon={<BrainCircuit size={14} />} />
            <MetricTile label="Rättade spel" value={performance.data.summary.settledBets} detail={`${performance.data.summary.wins} vunna · ${performance.data.summary.losses} förlorade · ${performance.data.summary.pushes} push`} icon={<Scale size={14} />} />
            <MetricTile label="P/L och ROI" value={percentage(performance.data.summary.roiPct)} detail={`${units(performance.data.summary.pnlUnits)} på ${units(performance.data.summary.stakeUnits)}`} tone={(performance.data.summary.roiPct ?? 0) >= 0 ? 'good' : 'bad'} icon={<TrendingUp size={14} />} />
            <MetricTile label="Officiell CLV" value={percentage(performance.data.summary.averageClvPct)} detail={`${percentage(performance.data.summary.clvBeatRatePct)} slår closing · ${performance.data.summary.officialClvObservations} obs`} tone={(performance.data.summary.averageClvPct ?? 0) >= 0 ? 'good' : 'bad'} icon={<Target size={14} />} />
          </section>

          <FormulaPerformanceFilters query={readQuery} facets={performance.data.facets} onChange={changeFilter} />

          <div className="formula-performance-explainer" role="note">
            <div><strong>Underlag före topplista.</strong><span>Raderna sorteras efter rättade spel och unika matcher, inte efter högst ROI.</span></div>
            <div><strong>CLV mäter priset.</strong><span>Positiv CLV betyder att oddset var bättre än den officiella T-10-closinglinan.</span></div>
            <div><strong>Kalibrering mäter sannolikheten.</strong><span>Brier visar hur väl sannolikheterna är kalibrerade. Lägre är bättre.</span></div>
          </div>

          {performance.data.groups.length ? (
            <FormulaPerformanceTable groups={performance.data.groups} />
          ) : (
            <StateNotice state="empty" title="Inga formelresultat matchar filtret" detail="Ändra formel, statkey, scope, period eller checkpoint. Inga värden fylls i artificiellt." />
          )}
          {performance.data.groups.length ? (
            <PaginationBar
              offset={offset}
              limit={limit}
              total={offset + performance.data.groups.length + (performance.data.page.hasMore ? 1 : 0)}
              hasMore={performance.data.page.hasMore}
              onPageChange={(value) => setSearchParams(patchSearchParams(searchParams, { offset: value }))}
            />
          ) : null}
        </>
      )}

      {model.isLoading ? (
        <StateNotice state="loading" title="Läser registrerad runtime" detail="Hämtar modell- och policystatus." />
      ) : model.isError || !model.data ? (
        <StateNotice state="failed" title="Runtime-status kunde inte läsas" detail="Skuggjämförelsen används inte som ersättning för saknad forward-status." />
      ) : <RuntimeProof data={model.data} />}
    </div>
  );
}
