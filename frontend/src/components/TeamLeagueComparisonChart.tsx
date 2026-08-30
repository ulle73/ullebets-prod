import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TeamStatChartRow } from '../domain/team-stats';

interface Props { title:string; subtitle:string; accessibleName:string; rows:TeamStatChartRow[]; }

const CHART_HEIGHT=420;

function barColor(value:number|null){if(value===null)return 'transparent';if(value>=5)return 'var(--chart-positive)';if(value<=-5)return 'var(--chart-negative)';return 'var(--chart-neutral)';}
function domainFor(rows:TeamStatChartRow[]):[number,number]{const maximum=Math.max(20,...rows.map((row)=>Math.abs(row.deviationPct??0)));const bound=Math.ceil(maximum/20)*20;return[-bound,bound];}
function tooltipValue(_value:unknown,name:unknown,props:unknown){const row=(props as {payload?:TeamStatChartRow})?.payload;return[row?.deviationLabel??'—',name==='deviationPct'?`${row?.label??'Stat'} · ${row?.periodLabel??''}`:String(name)];}

export function TeamLeagueComparisonChart({title,subtitle,accessibleName,rows}:Props){const hasComparableData=rows.some((row)=>row.deviationPct!==null);return <section className="team-comparison-chart" role="region" aria-label={accessibleName}>
 <header className="team-comparison-chart__header">
  <div><h2>{title}</h2><p>{subtitle}</p></div>
  <div className="team-comparison-chart__legend" aria-label="Förklaring"><span><i className="is-positive"/>Över ligasnitt</span><span><i className="is-neutral"/>Nära snitt</span><span><i className="is-negative"/>Under ligasnitt</span><span><i className="is-average"/>Ligasnitt</span></div>
 </header>
 <div className="team-comparison-chart__plot" aria-hidden="true">
  {hasComparableData?<ResponsiveContainer width="100%" height={CHART_HEIGHT} minWidth={0} initialDimension={{width:1100,height:CHART_HEIGHT}}><BarChart data={rows} margin={{top:30,right:16,bottom:8,left:2}}><CartesianGrid stroke="var(--color-border)" vertical={false}/><XAxis dataKey="rowKey" tick={false} axisLine={false} tickLine={false}/><YAxis domain={domainFor(rows)} tickFormatter={(value)=>`${value>0?'+':''}${value}%`} width={48} tick={{fill:'var(--color-text-muted)',fontSize:10}} axisLine={false} tickLine={false}/><ReferenceLine y={0} stroke="var(--chart-average)" strokeWidth={2}/><Tooltip cursor={{fill:'rgba(255,255,255,.025)'}} formatter={tooltipValue} contentStyle={{background:'var(--color-card)',border:'1px solid var(--color-border)',borderRadius:8,fontSize:11}}/><Bar dataKey="deviationPct" maxBarSize={28} isAnimationActive={false}>{rows.map((row)=><Cell key={row.rowKey} fill={barColor(row.deviationPct)}/>) }<LabelList dataKey="deviationLabel" position="top" fill="var(--color-text)" fontSize={9} fontWeight={700}/></Bar></BarChart></ResponsiveContainer>:<div className="team-comparison-chart__empty">Ligasnitt saknas för jämförelsen.</div>}
 </div>
 <div className="team-comparison-chart__values team-comparison-chart__values--all-periods" role="list" aria-label="Statvärden">{rows.map((row)=><div role="listitem" key={row.rowKey} data-stat-bar={row.rowKey} data-bar-origin="zero" className="team-comparison-chart__value"><strong>{row.valueLabel}</strong><span className="team-comparison-chart__axis-label"><span>{row.label}</span><small>{row.periodLabel}</small></span></div>)}</div>
</section>;}
