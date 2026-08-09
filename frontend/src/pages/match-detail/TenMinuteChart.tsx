import type { TenMinuteView } from './view-model';

type TeamSeries = TenMinuteView['home'];

function point(index: number, value: number, scaleMax: number): [number, number] {
  const x = 40 + (index / 8) * 820;
  const y = 130 - (value / Math.max(scaleMax, 1)) * 100;
  return [x, y];
}

function points(values: Array<number | null>, scaleMax: number): string {
  return values.flatMap((value, index) => value === null ? [] : [point(index, value, scaleMax).join(',')]).join(' ');
}

function TeamChart({ name, series, intervals, scaleMax, tone }: { name: string; series: TeamSeries; intervals: string[]; scaleMax: number; tone: 'home' | 'away' }) {
  const league = intervals.map((_, index) => {
    const forValue = series.leagueForValues[index] ?? null;
    const againstValue = series.leagueAgainstValues[index] ?? null;
    if (forValue === null && againstValue === null) return null;
    if (forValue === null) return againstValue;
    if (againstValue === null) return forValue;
    return (forValue + againstValue) / 2;
  });
  return (
    <figure className={`ten-chart ten-chart--${tone}`} aria-label={`${name} skott per 10 minuter`}>
      <figcaption>{name}</figcaption>
      <div className="ten-chart__plot">
        <svg viewBox="0 0 900 150" preserveAspectRatio="none" aria-hidden="true">
          <line className="ten-chart__grid" x1="40" y1="30" x2="860" y2="30" />
          <line className="ten-chart__grid" x1="40" y1="80" x2="860" y2="80" />
          <line className="ten-chart__grid" x1="40" y1="130" x2="860" y2="130" />
          <line className="ten-chart__half" x1="501" y1="18" x2="501" y2="138" />
          <polyline className="ten-chart__line ten-chart__line--league" points={points(league, scaleMax)} />
          <polyline className="ten-chart__line ten-chart__line--against" points={points(series.againstValues, scaleMax)} />
          <polyline className="ten-chart__line ten-chart__line--for" points={points(series.forValues, scaleMax)} />
          {series.forValues.map((value, index) => value === null ? null : <circle className="ten-chart__point ten-chart__point--for" cx={point(index, value, scaleMax)[0]} cy={point(index, value, scaleMax)[1]} r="4" key={`for-${intervals[index]}`} />)}
          {series.againstValues.map((value, index) => value === null ? null : <circle className="ten-chart__point ten-chart__point--against" cx={point(index, value, scaleMax)[0]} cy={point(index, value, scaleMax)[1]} r="4" key={`against-${intervals[index]}`} />)}
        </svg>
        <div className="ten-chart__labels">{intervals.map((interval) => <span key={interval}>{interval}</span>)}</div>
      </div>
      <ul className="sr-only">
        {intervals.map((interval, index) => <li key={interval}>{interval}: för {series.forValues[index] ?? 'saknas'}, emot {series.againstValues[index] ?? 'saknas'}</li>)}
      </ul>
    </figure>
  );
}

export function TenMinuteChart({ view, homeName, awayName }: { view: TenMinuteView; homeName: string; awayName: string }) {
  return (
    <section className="analytics-panel ten-minute-panel">
      <header className="analytics-section-title">
        <h2>Skott per 10 min</h2>
        <span className="chart-legend"><i className="legend-swatch legend-swatch--for" />För<i className="legend-swatch legend-swatch--against" />Emot<i className="legend-line" />Ligasnitt</span>
      </header>
      <TeamChart name={homeName} series={view.home} intervals={view.intervals} scaleMax={view.scaleMax} tone="home" />
      <TeamChart name={awayName} series={view.away} intervals={view.intervals} scaleMax={view.scaleMax} tone="away" />
    </section>
  );
}
