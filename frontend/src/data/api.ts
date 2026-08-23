import type { RichLeagueResponse, RichMatchDetailResponse, RichTeamResponse } from '../domain/drilldown-types';
import type { AutoResponse, DashboardResponse, MatchesResponse, ModelResponse, ResultsResponse, SystemResponse } from '../domain/types';

type QueryValue = string | number | boolean | null | undefined;
export type ApiQuery = Record<string, QueryValue>;
export interface AutoQuery extends ApiQuery { limit?:number;offset?:number;league?:string;stat?:string;period?:string;scope?:string;direction?:string;model?:string;policy?:string;checkpoint?:string; }
export interface ResultsQuery extends ApiQuery { limit?:number;offset?:number;status?:string;league?:string;stat?:string;period?:string;scope?:string;direction?:string;model?:string;policy?:string;checkpoint?:string; }

export function buildApiUrl(path:string,query:ApiQuery={}):string{const params=new URLSearchParams();for(const[key,value]of Object.entries(query)){if(value===undefined||value===null||value==='')continue;params.set(key,String(value));}const suffix=params.toString();return `/api/v1${path}${suffix?`?${suffix}`:''}`;}
async function getJson<T>(url:string,signal?:AbortSignal):Promise<T>{const init:RequestInit={method:'GET',headers:{Accept:'application/json'}};if(signal)init.signal=signal;const response=await fetch(url,init);if(!response.ok)throw new Error(`Read API returned ${response.status}`);return response.json() as Promise<T>;}
export function fetchDashboard(date?:string,signal?:AbortSignal):Promise<DashboardResponse>{return getJson(buildApiUrl('/dashboard',{date}),signal);}
export function fetchMatches(matchKeys:string[],signal?:AbortSignal):Promise<MatchesResponse>{const keys=Array.from(new Set(matchKeys.filter(Boolean))).join(',');return getJson(buildApiUrl('/matches',{keys}),signal);}
export function fetchMatchDetail(matchKey:string,signal?:AbortSignal):Promise<RichMatchDetailResponse>{return getJson(buildApiUrl(`/matches/${encodeURIComponent(matchKey)}`),signal);}
export function fetchLeague(leagueKey:string,signal?:AbortSignal):Promise<RichLeagueResponse>{return getJson(buildApiUrl(`/leagues/${encodeURIComponent(leagueKey)}`),signal);}
export function fetchAuto(query:AutoQuery={},signal?:AbortSignal):Promise<AutoResponse>{return getJson(buildApiUrl('/auto',query),signal);}
export function fetchResults(query:ResultsQuery={},signal?:AbortSignal):Promise<ResultsResponse>{return getJson(buildApiUrl('/results',query),signal);}
export function fetchTeam(teamKey:string,signal?:AbortSignal):Promise<RichTeamResponse>{return getJson(buildApiUrl(`/teams/${encodeURIComponent(teamKey)}`),signal);}
export function fetchModel(signal?:AbortSignal):Promise<ModelResponse>{return getJson(buildApiUrl('/model'),signal);}
export function fetchSystem(signal?:AbortSignal):Promise<SystemResponse>{return getJson(buildApiUrl('/system'),signal);}
