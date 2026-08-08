import { CircleSlash2, CircleX, Trophy } from 'lucide-react';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { operationalResultsSnapshot } from '../data/product-snapshots';

export function ResultsLoopPage() {
  const snapshot = operationalResultsSnapshot;
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Operational forward results" title="Resultatloop" subtitle="Öppna, avgjorda och exkluderade rader hålls isär. Operationsutfall är inte automatiskt V6-proof." />
      <div className="metric-tile-grid metric-tile-grid--4">
        <MetricTile label="Giltigt avgjorda" value={snapshot.settled} detail="Sparad operationssnapshot" tone="brand" />
        <MetricTile label="Vinster" value={snapshot.wins} detail="Operational rows" tone="good" icon={<Trophy size={14} />} />
        <MetricTile label="Förluster" value={snapshot.losses} detail="Operational rows" tone="bad" icon={<CircleX size={14} />} />
        <MetricTile label="Timing-exkluderade" value={snapshot.excludedTiming} detail="Kvar för audit, ej performance" tone="warn" icon={<CircleSlash2 size={14} />} />
      </div>
      <StateNotice state="excluded" title="Timing-exkluderade är inte förluster" detail="Tre rader som bryter prediction-freeze-timingen finns kvar för audit men får inte PnL, ROI eller CLV." />
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Verifierat post-match-exempel</p><h2>{snapshot.coritibaCruzeiro.match}</h2></div><span className="result-score">{snapshot.coritibaCruzeiro.result}</span></div>
        <div className="result-summary-row"><span><strong>{snapshot.coritibaCruzeiro.forwardRows}</strong> forward-rader</span><span className="positive-text"><strong>{snapshot.coritibaCruzeiro.wins}</strong> vinster</span><span className="negative-text"><strong>{snapshot.coritibaCruzeiro.losses}</strong> förluster</span></div>
      </section>
    </div>
  );
}
