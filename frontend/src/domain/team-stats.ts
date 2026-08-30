import type { RichTeamProfileContext, RichTeamResponse } from './drilldown-types';
import type { TeamProfileStatNode } from './types';

export type ProfileContextKey='home'|'away';
export type Orientation='for'|'against';
export interface TeamStatInsight{context:ProfileContextKey;orientation:Orientation;statKey:string;period:string;value:number;rank:number|null;leagueAverage:number|null;deviationPct:number|null;}

export const TEAM_PROFILE_STATS = [
 {statKey:'shotsOnGoal',label:'Skott på mål'},
 {statKey:'totalShots',label:'Skott'},
 {statKey:'cornerKicks',label:'Hörnor'},
 {statKey:'yellowCards',label:'Gula kort'},
 {statKey:'freeKicks',label:'Frisparkar'},
 {statKey:'fouls',label:'Fouls'},
 {statKey:'totalTackle',label:'Tacklingar'},
 {statKey:'offsides',label:'Offsides'},
 {statKey:'goalKicks',label:'Insparkar'},
 {statKey:'throwIns',label:'Inkast'},
] as const;

export const TEAM_PROFILE_PERIODS = [
 {period:'ALL',label:'Totalt'},
 {period:'1ST',label:'1:a halvlek'},
 {period:'2ND',label:'2:a halvlek'},
] as const;

export interface TeamStatChartRow{rowKey:string;statKey:string;label:string;period:string;periodLabel:string;value:number|null;leagueAverage:number|null;deviationPct:number|null;deviationLabel:string;valueLabel:string;}

function nodeValue(node:TeamProfileStatNode|undefined):number|null{return typeof node?.value==='number'?node.value:null;}
export function deviationPct(value:number,average:number|null):number|null{return average===null||average===0?null:((value-average)/average)*100;}

export function flattenContext(context:RichTeamProfileContext|null,contextKey:ProfileContextKey):TeamStatInsight[]{if(!context)return[];const out:TeamStatInsight[]=[];for(const orientation of ['for','against'] as const){const stats=context.statistics[orientation]??{};const averages=context.statistics.leagueAverage?.[orientation]??{};for(const[statKey,periods]of Object.entries(stats)){for(const[period,node]of Object.entries(periods)){const value=nodeValue(node);if(value===null)continue;const avg=nodeValue(averages[statKey]?.[period]);out.push({context:contextKey,orientation,statKey,period,value,rank:typeof node.rank==='number'?node.rank:null,leagueAverage:avg,deviationPct:deviationPct(value,avg)});}}}return out;}
export function allTeamInsights(team:RichTeamResponse):TeamStatInsight[]{return[...flattenContext(team.contexts.home,'home'),...flattenContext(team.contexts.away,'away')];}
export function strongestDeviations(team:RichTeamResponse,limit=4){const rows=allTeamInsights(team);const above=rows.filter((row)=>row.deviationPct!==null&&row.deviationPct>0).sort((a,b)=>(b.deviationPct??0)-(a.deviationPct??0)).slice(0,limit);const below=rows.filter((row)=>row.deviationPct!==null&&row.deviationPct<0).sort((a,b)=>(a.deviationPct??0)-(b.deviationPct??0)).slice(0,limit);return{above,below};}

export function buildTeamStatChartRows(context:RichTeamProfileContext|null,contextKey:ProfileContextKey,orientation:Orientation):TeamStatChartRow[]{const insights=flattenContext(context,contextKey);const lookup=new Map(insights.filter((row)=>row.orientation===orientation).map((row)=>[`${row.statKey}:${row.period}`,row]));const rows=TEAM_PROFILE_STATS.flatMap(({statKey,label})=>TEAM_PROFILE_PERIODS.map(({period,label:periodLabel})=>{const row=lookup.get(`${statKey}:${period}`);const deviation=row?.deviationPct??null;return{rowKey:`${statKey}:${period}`,statKey,label,period,periodLabel,value:row?.value??null,leagueAverage:row?.leagueAverage??null,deviationPct:deviation,deviationLabel:deviation===null?'—':`${deviation>0?'+':''}${deviation.toLocaleString('sv-SE',{maximumFractionDigits:0})}%`,valueLabel:row?.value?.toLocaleString('sv-SE',{maximumFractionDigits:2})??'—'};}));return rows.sort((left,right)=>{if(left.deviationPct===null)return right.deviationPct===null?0:1;if(right.deviationPct===null)return-1;return right.deviationPct-left.deviationPct;});}
