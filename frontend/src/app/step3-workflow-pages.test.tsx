import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const dashboard={selectedDate:'2026-08-13',timezone:'Europe/Stockholm',generatedAt:'2026-08-12T20:00:00Z',matchupSource:'missing',matches:[],matchups:[]};
const selection={selectionKey:'s1',predictionKey:'p1',matchKey:'m1',leagueKey:'league-a',leagueName:'League A',homeTeamKey:'home',awayTeamKey:'away',homeTeamName:'Home FC',awayTeamName:'Away FC',statKey:'fouls',period:'ALL',scope:'away',direction:'over',lineValue:12.5,selectedOdds:1.9,predictedWinProbability:.61,expectedRoiUnits:.159,modelId:'v6',modelStatus:'forward_test_only',policyId:'policy-1',policyStatus:'shadow',snapshotKey:null,offerKey:null,oddsSnapshotTime:null,predictionCreatedAt:null,matchStartTime:'2026-08-13T18:00:00Z',validForForwardEvaluation:true,invalidForModel:false};
const result={resultLoopKey:'r1',predictionKey:'p1',selectionKey:'s1',trackingKey:null,matchKey:'m1',leagueKey:'league-a',leagueName:'League A',homeTeamKey:'home',awayTeamKey:'away',homeTeamName:'Home FC',awayTeamName:'Away FC',statKey:'fouls',period:'ALL',scope:'away',direction:'over',lineValue:12.5,savedOdds:1.9,savedAt:'2026-08-13T16:00:00Z',oddsSnapshotTime:null,predictionCreatedAt:null,matchStartTime:'2026-08-13T18:00:00Z',settlementStatus:'settled',settlementResult:'win',actualValue:14,homeValue:null,awayValue:null,win:true,roiUnits:.9,pnlUnits:.9,stakeUnits:1,actualSource:'sofascore',actualSourceStatus:'verified',settledAt:'2026-08-13T21:00:00Z',validForPerformance:true,invalidForModel:false,resultLoopStatus:'settled',statusReason:null,openingOdds:null,latestObservedOdds:null,closingOdds:1.8,closingQuality:'t10',closingSnapshotLabel:'T-10',closingSnapshotTime:null,officialClv:true,clvBasis:null,clvStatus:'available',clvPct:5.5,beatClosingLine:true,prematchObservationCount:3,refreshedAt:null};

function urls(fetchMock: ReturnType<typeof renderApp>['fetchMock'], path:string){return fetchMock.mock.calls.map(([input])=>typeof input==='string'?input:input instanceof URL?input.toString():input.url).filter((value)=>value.startsWith(path));}
function params(url:string){return new URLSearchParams(url.split('?')[1]??'');}
function main(){return within(screen.getByRole('main'));}

describe('step 3 workflow pages',()=>{
 it('Auto consumes shareable filters and server pagination',async()=>{
  const{fetchMock}=renderApp('/auto?stat=fouls&direction=over&scope=away&period=ALL&limit=25&offset=50',{
   '/api/v1/dashboard':dashboard,
   '/api/v1/auto':{summary:{total:80,valid:70,excluded:10},page:{limit:25,offset:50,hasMore:true},selections:[selection]},
  });
  expect(await main().findByRole('heading',{name:'Auto'})).toBeInTheDocument();
  await waitFor(()=>{const call=urls(fetchMock,'/api/v1/auto').at(-1);expect(call).toBeDefined();expect(params(call!).get('stat')).toBe('fouls');expect(params(call!).get('direction')).toBe('over');expect(params(call!).get('scope')).toBe('away');expect(params(call!).get('period')).toBe('ALL');expect(params(call!).get('limit')).toBe('25');expect(params(call!).get('offset')).toBe('50');});
  fireEvent.click(main().getByRole('button',{name:'Nästa sida'}));
  await waitFor(()=>expect(params(urls(fetchMock,'/api/v1/auto').at(-1)!).get('offset')).toBe('75'));
  expect(main().getByRole('button',{name:'Föregående sida'})).toBeEnabled();
 });

 it('Resultatloop sends status filters to the read API and paginates',async()=>{
  const{fetchMock}=renderApp('/resultatloop?status=settled&stat=fouls&direction=over&limit=20&offset=20',{
   '/api/v1/dashboard':dashboard,
   '/api/v1/results':{summary:{rows:45,settled:40,wins:24,losses:16,pushes:0,excluded:5},page:{limit:20,offset:20,hasMore:true},rows:[result]},
  });
  expect(await main().findByRole('heading',{name:'Resultatloop'})).toBeInTheDocument();
  await waitFor(()=>{const query=params(urls(fetchMock,'/api/v1/results').at(-1)!);expect(query.get('status')).toBe('settled');expect(query.get('stat')).toBe('fouls');expect(query.get('direction')).toBe('over');expect(query.get('offset')).toBe('20');});
  fireEvent.click(main().getByRole('button',{name:'Nästa sida'}));
  await waitFor(()=>expect(params(urls(fetchMock,'/api/v1/results').at(-1)!).get('offset')).toBe('40'));
 });

 it('Historik renders persisted result rows instead of only aggregate counters',async()=>{
  renderApp('/historik',{
   '/api/v1/dashboard':dashboard,
   '/api/v1/results':{summary:{rows:1,settled:1,wins:1,losses:0,pushes:0,excluded:0},page:{limit:50,offset:0,hasMore:false},rows:[result]},
  });
  expect(await main().findByRole('heading',{name:'Historik'})).toBeInTheDocument();
  expect(main().getByRole('heading',{name:'Historikrader'})).toBeInTheDocument();
  expect(main().getByRole('link',{name:'Home FC'})).toHaveAttribute('href','/lag/home');
  expect(main().getByRole('link',{name:'Away FC'})).toHaveAttribute('href','/lag/away');
  expect(main().getByRole('link',{name:/Öppna Home FC.*Away FC/})).toHaveAttribute('href','/matcher/m1');
  expect(main().getByText('+0,9 u')).toBeInTheDocument();
  expect(main().getByText(/CLV \+5,5 %/)).toBeInTheDocument();
 });
});
