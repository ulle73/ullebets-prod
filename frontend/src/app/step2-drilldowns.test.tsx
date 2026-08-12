import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const emptyDashboard={selectedDate:'2026-08-13',timezone:'Europe/Stockholm',generatedAt:'2026-08-12T20:00:00Z',matchupSource:'missing',matches:[],matchups:[]};
const match={matchKey:'m1',sourceMatchId:1,sourceDate:'2026-08-13',startTime:'2026-08-13T18:00:00Z',leagueKey:'league-a',leagueName:'League A',homeTeamKey:'home',awayTeamKey:'away',homeTeamName:'Home FC',awayTeamName:'Away FC',statusType:'finished',state:'finished',homeScore:1,awayScore:2,resultFetchedAt:'2026-08-13T21:00:00Z'};

function main(){return within(screen.getByRole('main'));}

describe('step 2 drilldown pages',()=>{
 it('team page exposes home/away, for/against, strongest deviations and clickable history',async()=>{
  renderApp('/lag/home',{'/api/v1/dashboard':emptyDashboard,'/api/v1/teams/home':{
   team:{teamKey:'home',leagueKey:'league-a',teamId:1,teamName:'Home FC',teamImageUrl:null,optaId:null,optaRank:22,optaRating:81.2,capturedAt:null},
   league:{leagueKey:'league-a',leagueName:'League A',leagueId:1,country:'SE',seasonId:2026,categoryId:null,groupId:null,capturedAt:null},
   contexts:{home:{profileKey:'p',profileDate:'current',generatedAt:'2026-08-12T20:00:00Z',matchType:'home',leagueTeamCount:18,savedAt:null,games:[{matchId:77,matchKey:'past-77',date:'2026-08-10',timestamp:null,opponentName:'Opponent FC',opponentTeamKey:'opp',homeScore:2,awayScore:1}],statistics:{for:{fouls:{ALL:{value:13,rank:2,history:[]}}},against:{fouls:{ALL:{value:8,rank:15,history:[]}}},leagueAverage:{for:{fouls:{ALL:{value:10}}},against:{fouls:{ALL:{value:10}}}}},specials:{firstGoal:{scoreFirstPercentage:0.6}},behaviour:null},away:null},matches:[]
  }});
  expect(await main().findByRole('heading',{name:'Home FC'})).toBeInTheDocument();
  expect(main().getByRole('button',{name:'Hemmaprofil'})).toBeInTheDocument();
  expect(main().getByRole('button',{name:'FOR'})).toBeInTheDocument();
  expect(main().getByText('Största avvikelser mot ligan')).toBeInTheDocument();
  expect(main().getByText('+30,0 %')).toBeInTheDocument();
  expect(main().getByText('−20,0 %')).toBeInTheDocument();
  expect(main().getByRole('link',{name:/Opponent FC/})).toHaveAttribute('href','/lag/opp');
  expect(main().getByRole('link',{name:/2–1/})).toHaveAttribute('href','/matcher/past-77');
 });

 it('league page provides stat explorer rankings backed by teamprofile rows',async()=>{
  renderApp('/liga/league-a',{'/api/v1/dashboard':emptyDashboard,'/api/v1/leagues/league-a':{
   league:{leagueKey:'league-a',leagueName:'League A',leagueId:1,country:'SE',seasonId:2026,categoryId:null,groupId:null,capturedAt:null},
   teams:[{teamKey:'home',leagueKey:'league-a',teamId:1,teamName:'Home FC',teamImageUrl:null,optaId:null,optaRank:22,optaRating:81.2,capturedAt:null}],ranking:null,matches:[match],
   statRows:[{teamKey:'home',teamName:'Home FC',context:'home',orientation:'for',statKey:'fouls',period:'ALL',value:13,rank:2,leagueAverage:10}]
  }});
  expect(await main().findByRole('heading',{name:'League A'})).toBeInTheDocument();
  expect(main().getByRole('heading',{name:'Statistikranking'})).toBeInTheDocument();
  expect(main().getByText('#2')).toBeInTheDocument();
  expect(main().getByText('+30,0 %')).toBeInTheDocument();
 });

 it('match page shows result, market odds, actuals and registered forward evidence',async()=>{
  renderApp('/matcher/m1',{'/api/v1/dashboard':emptyDashboard,'/api/v1/matches/m1':{
   match,matchups:[],matchupSource:'missing',leagueAverageMatchups:[],checkpoints:[],teamStats:[],result:{homeScore:1,awayScore:2,fetchedAt:null,mappingConfidence:'exact',hasMatchDetails:true,hasIncidents:true,hasShotmap:true},
   actualStats:[{statKey:'fouls',period:'ALL',scope:'away',actualValue:14,mappingConfidence:'exact'}],marketOffers:[{offerKey:'o1',eventId:'e1',statKey:'fouls',scope:'away',period:'ALL',line:12.5,overOdds:1.9,underOdds:1.8,sourceProvider:'kambi',payloadKind:'kambi',updatedAt:'2026-08-13T15:00:00Z'}],
   forwardSelections:[{selectionKey:'s1',predictionKey:'p1',matchKey:'m1',leagueKey:'league-a',leagueName:'League A',homeTeamKey:'home',awayTeamKey:'away',homeTeamName:'Home FC',awayTeamName:'Away FC',statKey:'fouls',period:'ALL',scope:'away',direction:'over',lineValue:12.5,selectedOdds:1.9,predictedWinProbability:0.61,expectedRoiUnits:0.159,modelId:'v6',modelStatus:'forward_test_only',policyId:'p',policyStatus:null,snapshotKey:null,offerKey:null,oddsSnapshotTime:null,predictionCreatedAt:null,matchStartTime:null,validForForwardEvaluation:true,invalidForModel:false}],
   forwardResults:[{resultLoopKey:'r1',predictionKey:'p1',selectionKey:'s1',trackingKey:null,matchKey:'m1',leagueKey:'league-a',leagueName:'League A',homeTeamKey:'home',awayTeamKey:'away',homeTeamName:'Home FC',awayTeamName:'Away FC',statKey:'fouls',period:'ALL',scope:'away',direction:'over',lineValue:12.5,savedOdds:1.9,savedAt:null,oddsSnapshotTime:null,predictionCreatedAt:null,matchStartTime:null,settlementStatus:'settled',settlementResult:'win',actualValue:14,homeValue:null,awayValue:null,win:true,roiUnits:.9,pnlUnits:.9,stakeUnits:1,actualSource:null,actualSourceStatus:null,settledAt:null,validForPerformance:true,invalidForModel:false,resultLoopStatus:'settled',statusReason:null,openingOdds:null,latestObservedOdds:null,closingOdds:1.8,closingQuality:'t10',closingSnapshotLabel:'T-10',closingSnapshotTime:null,officialClv:true,clvBasis:null,clvStatus:'available',clvPct:5.5,beatClosingLine:true,prematchObservationCount:3,refreshedAt:null}]
  }});
  expect(await main().findByText('1–2')).toBeInTheDocument();
  expect(main().getByRole('heading',{name:'Marknadsodds'})).toBeInTheDocument();
  expect(main().getByText('1,90')).toBeInTheDocument();
  expect(main().getByRole('heading',{name:'Utfall & forward-evidens'})).toBeInTheDocument();
  expect(main().getByText('CLV +5,5 %')).toBeInTheDocument();
 });
});
