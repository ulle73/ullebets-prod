import { Database, RadioTower, ShieldCheck } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useSystemStatus } from '../data/queries';

function text(row: Record<string, unknown>, key: string): string {
  const value = row[key];
  return value === null || value === undefined || value === '' ? '—' : String(value);
}

export function SystemStatusPage() {
  const query = useSystemStatus();
  if (query.isLoading) return <StateNotice state="loading" title="Läser systemstatus" detail="Hämtar job_runs, health_reports och audit_reports från V2." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Systemstatus kunde inte läsas" detail="Frontend visar ingen gammal verifieringssnapshot som ersättning." />;

  const data = query.data;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="V2 data & operations" title="Systemstatus" subtitle="Statusen kommer från aktuella persistenta operationscollections." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Job runs" value={data.jobs.length} detail="Senast lästa" icon={<RadioTower size={14} />} />
        <MetricTile label="Health reports" value={data.health.length} detail="Senast lästa" tone="brand" icon={<ShieldCheck size={14} />} />
        <MetricTile label="Audit reports" value={data.audits.length} detail="Senast lästa" icon={<Database size={14} />} />
      </div>
      {data.jobs.length === 0 ? <StateNotice state="empty" title="Inga job_runs" detail="V2 returnerade ingen jobbhistorik." /> : (
        <section className="result-table" aria-label="Senaste jobb">
          {data.jobs.map((row, index) => (
            <article className="result-row" key={`${text(row, 'run_id')}:${index}`}>
              <div><strong>{text(row, 'job_name')}</strong><small>{text(row, 'source_workflow')}</small></div>
              <span>{text(row, 'status')}</span><span>{text(row, 'started_at')}</span><span>{text(row, 'finished_at')}</span>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
