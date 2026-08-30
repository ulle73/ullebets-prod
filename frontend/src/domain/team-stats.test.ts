import { describe, expect, it } from 'vitest';
import type { RichTeamProfileContext } from './drilldown-types';
import { buildTeamStatChartRows } from './team-stats';

function profileContext():RichTeamProfileContext{return {
 profileKey:'profile',profileDate:'2026-08-30',generatedAt:null,matchType:'home',leagueTeamCount:18,savedAt:null,games:[],specials:null,behaviour:null,
 statistics:{
  for:{
   shotsOnGoal:{ALL:{value:13},'1ST':{value:8},'2ND':{value:4}},
   totalShots:{ALL:{value:12}},
  },
  against:{},
  leagueAverage:{for:{shotsOnGoal:{ALL:{value:10},'1ST':{value:4},'2ND':{value:8}},totalShots:{ALL:{value:10}}},against:{}},
 },
};}

describe('buildTeamStatChartRows',()=>{
 it('returns all stat-period combinations sorted by descending league deviation',()=>{
  const rows=buildTeamStatChartRows(profileContext(),'home','for');

  expect(rows).toHaveLength(30);
  expect(new Set(rows.map((row)=>`${row.statKey}:${row.period}`)).size).toBe(30);
  expect(rows.slice(0,4).map((row)=>`${row.statKey}:${row.period}:${row.deviationPct}`)).toEqual([
   'shotsOnGoal:1ST:100',
   'shotsOnGoal:ALL:30',
   'totalShots:ALL:20',
   'shotsOnGoal:2ND:-50',
  ]);
  expect(rows.slice(4).every((row)=>row.deviationPct===null)).toBe(true);
 });
});
