import type { RichTeamProfileContext, RichTeamResponse } from './drilldown-types';
import type { TeamProfileStatNode } from './types';

export type ProfileContextKey='home'|'away';
export type Orientation='for'|'against';
export interface TeamStatInsight{context:ProfileContextKey;orientation:Orientation;statKey:string;period:string;value:number;rank:number|null;leagueAverage:number|null;deviationPct:number|null;}

function nodeValue(node:TeamProfileStatNode|undefined):number|null{return typeof node?.value==='number'?node.value:null;}
export function deviationPct(value:number,average:number|null):number|null{return average===null||average===0?null:((value-average)/average)*100;}

export function flattenContext(context:RichTeamProfileContext|null,contextKey:ProfileContextKey):TeamStatInsight[]{if(!context)return[];const out:TeamStatInsight[]=[];for(const orientation of ['for','against'] as const){const stats=context.statistics[orientation]??{};const averages=context.statistics.leagueAverage?.[orientation]??{};for(const[statKey,periods]of Object.entries(stats)){for(const[period,node]of Object.entries(periods)){const value=nodeValue(node);if(value===null)continue;const avg=nodeValue(averages[statKey]?.[period]);out.push({context:contextKey,orientation,statKey,period,value,rank:typeof node.rank==='number'?node.rank:null,leagueAverage:avg,deviationPct:deviationPct(value,avg)});}}}return out;}
export function allTeamInsights(team:RichTeamResponse):TeamStatInsight[]{return[...flattenContext(team.contexts.home,'home'),...flattenContext(team.contexts.away,'away')];}
export function strongestDeviations(team:RichTeamResponse,limit=4){const rows=allTeamInsights(team);const above=rows.filter((row)=>row.deviationPct!==null&&row.deviationPct>0).sort((a,b)=>(b.deviationPct??0)-(a.deviationPct??0)).slice(0,limit);const below=rows.filter((row)=>row.deviationPct!==null&&row.deviationPct<0).sort((a,b)=>(a.deviationPct??0)-(b.deviationPct??0)).slice(0,limit);return{above,below};}
