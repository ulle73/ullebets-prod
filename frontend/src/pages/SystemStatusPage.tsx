import { ClipboardCheck, RadioTower, ShieldCheck } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useSystemStatus } from '../data/queries';

function primitive(row: Record<string, unknown>, key: string): string | null {
  const value = row[key];
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : null;
}

function firstText(row: Record<string, unknown>, keys: string[], fallback = '—'): string {
  for (const key of keys) {
    const value = primitive(row, key);
    if (value) return value;
  }
  return fallback;
}

function statusClass(status: string): string {
  const normalized = status.toLocaleLowerCase('sv-SE');
  if (['verified', 'success', 'succeeded', 'ok', 'healthy'].includes(normalized)) return 'status-badge status-badge--verified';
  if (normalized === 'partial') return 'status-badge status-badge--partial';
  if (['unproven', 'blocked', 'failed', 'failure'].includes(normalized)) return 'status-badge status-badge--unproven';
  return 'status-badge';
}

function StatusBadge({ value }: { value: string }) {
  return <span className={statusClass(value)}>{value.toLocaleUpperCase('sv-SE')}</span>;
}

function OperationsRows({ rows, kind }: { rows: Record<string, unknown>[]; kind: 'jobs' | 'health' | 'audits' }) {
  return (
    <div className="result-table">
      {rows.map((row, index) => {
        const title = kind === 'jobs'
          ? firstText(row, ['job_name', 'name'], 'Jobb')
          : kind === 'health'
            ? firstText(row, ['check_name', 'name', 'report_name'], 'Health-kontroll')
            : firstText(row, ['audit_name', 'name', 'report_name'], 'Audit');
        const status = firstText(row, ['status', 'state'], 'unknown');
        const source = kind === 'jobs'
          ? firstText(row, ['source_workflow', 'workflow'], 'Workflow saknas')
          : firstText(row, ['message', 'detail', 'reason'], 'Ingen detalj registrerad');
        const started = firstText(row, ['started_at', 'generated_at', 'created_at', 'captured_at']);
        const finished = firstText(row, ['finished_at', 'updated_at', 'generated_at']);
        const key = firstText(row, ['run_id', 'report_id', 'check_id', 'audit_id'], `${kind}:${index}`);
        return (
          <article className="result-row" key={key}>
            <div className="result-row__identity"><strong>{title}</strong><small>{source}</small></div>
            <span><StatusBadge value={status} /></span>
            <span>{started}</span>
            <span>{finished}</span>
            <span>{kind === 'jobs' ? firstText(row, ['duration_seconds', 'attempt'], '') : ''}</span>
          </article>
        );
      })}
    </div>
  );
}

export function SystemStatusPage() {
  const query = useSystemStatus();
  if (query.isLoading) return <StateNotice state="loading" title="Läser systemstatus" detail="Hämtar senaste jobb, health-kontroller och audits." />;
  if (query.isError || !query.data) return <StateNotice state="failed" title="Systemstatus kunde inte läsas" detail="Frontend visar ingen gammal verifieringssnapshot som ersättning." />;

  const data = query.data;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Data & operations" title="Systemstatus" subtitle="Aktuell operationsstatus från read-lagret. Statusar återges som de är registrerade och fylls inte i av frontend." />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Jobb" value={data.jobs.length} detail="Senast lästa" icon={<RadioTower size={14} />} />
        <MetricTile label="Health" value={data.health.length} detail="Registrerade kontroller" tone="brand" icon={<ShieldCheck size={14} />} />
        <MetricTile label="Audits" value={data.audits.length} detail="Registrerade granskningar" icon={<ClipboardCheck size={14} />} />
      </div>

      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Operations</p><h2>Senaste jobb</h2></div></div>
        {data.jobs.length ? <OperationsRows rows={data.jobs} kind="jobs" /> : <StateNotice state="empty" title="Inga jobb registrerade" detail="Ingen jobbhistorik finns i den aktuella läsvyn." />}
      </section>
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Datakvalitet</p><h2>Health</h2></div></div>
        {data.health.length ? <OperationsRows rows={data.health} kind="health" /> : <StateNotice state="empty" title="Inga health-kontroller" detail="Ingen aktuell health-status finns registrerad." />}
      </section>
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Verifiering</p><h2>Audits</h2></div></div>
        {data.audits.length ? <OperationsRows rows={data.audits} kind="audits" /> : <StateNotice state="empty" title="Inga audits" detail="Ingen aktuell audit-status finns registrerad." />}
      </section>
    </div>
  );
}
