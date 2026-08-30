import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { EntityLink } from '../components/EntityLink';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { TeamLeagueComparisonChart } from '../components/TeamLeagueComparisonChart';
import { useTeam } from '../data/queries';
import { buildTeamStatChartRows, type ProfileContextKey } from '../domain/team-stats';

const PERIODS=[{key:'ALL',label:'Hela matchen',short:'Totalt'},{key:'1ST',label:'Första halvlek',short:'1:a halvlek'},{key:'2ND',label:'Andra halvlek',short:'2:a halvlek'}] as const;

export function TeamPage(){
 const{teamId}=useParams();const query=useTeam(teamId);const[contextKey,setContextKey]=useState<ProfileContextKey>('home');const[period,setPeriod]=useState('ALL');
 if(query.isLoading)return <StateNotice state="loading" title="Hämtar lagprofil" detail="Läser lagets statistik och ligaranking."/>;
 if(query.isError||!query.data)return <StateNotice state="empty" title="Lagprofil saknas" detail="Ingen lagprofil kunde hittas."/>;
 const data=query.data;const{team,league,contexts}=data;const availableContext=contexts[contextKey]??contexts.home??contexts.away;const activeKey:ProfileContextKey=contexts[contextKey]?contextKey:contexts.home?'home':'away';
 const forRows=buildTeamStatChartRows(availableContext,activeKey,'for',period);const againstRows=buildTeamStatChartRows(availableContext,activeKey,'against',period);const periodLabel=PERIODS.find((item)=>item.key===period)?.short??period;
 return <div className="page-stack team-profile-page">
  <PageHeader eyebrow={league?.leagueName??'Lagprofil'} title={team.teamName??team.teamKey} subtitle={[team.optaRank!==null?`Opta #${team.optaRank}`:null,team.optaRating!==null?`Rating ${team.optaRating.toLocaleString('sv-SE')}`:null].filter(Boolean).join(' · ')||'Liga-relativ lagstatistik'} aside={league?<EntityLink kind="league" id={league.leagueKey} className="quiet-link">Öppna ligan</EntityLink>:undefined}/>
  <section className="profile-controls team-profile-page__controls" aria-label="Lagprofilfilter">
   <div><span>Spelplats</span><div className="segmented">{(['home','away'] as const).map((key)=><button type="button" key={key} disabled={!contexts[key]} className={activeKey===key?'is-active':''} onClick={()=>setContextKey(key)} aria-label={key==='home'?'Hemmaprofil':'Bortaprofil'}>{key==='home'?'Hemma':'Borta'}</button>)}</div></div>
   <div><span>Period</span><div className="segmented">{PERIODS.map(({key,label,short})=><button type="button" key={key} className={period===key?'is-active':''} onClick={()=>setPeriod(key)} aria-label={label}>{short}</button>)}</div></div>
  </section>
  {!availableContext?<StateNotice state="empty" title="Teamprofile-data saknas" detail="Ingen aktuell hemma- eller bortaprofil finns."/>:<>
   <TeamLeagueComparisonChart title={`${team.teamName} · FÖR`} subtitle={`Lagets egna nyckeltal · ${activeKey==='home'?'hemma':'borta'} · ${periodLabel}`} accessibleName="Lagets statistik jämfört med ligan" rows={forRows}/>
   <TeamLeagueComparisonChart title={`${team.teamName} · MOT`} subtitle={`Motståndarnas nyckeltal mot laget · ${activeKey==='home'?'hemma':'borta'} · ${periodLabel}`} accessibleName="Motståndarnas statistik mot laget jämfört med ligan" rows={againstRows}/>
   {availableContext.games.length?<section className="product-section"><div className="section-heading"><div><p className="eyebrow">Historik</p><h2>Matcher i profilen</h2></div></div><div className="entity-list">{availableContext.games.map((game,index)=><article className="entity-row" key={`${game.matchKey??game.matchId??index}`}><time>{game.date??'—'}</time><div className="entity-row__main"><EntityLink kind="team" id={game.opponentTeamKey}>{game.opponentName??'Okänd motståndare'}</EntityLink></div>{game.homeScore!==null&&game.awayScore!==null?<EntityLink kind="match" id={game.matchKey}>{game.homeScore}–{game.awayScore}</EntityLink>:<EntityLink kind="match" id={game.matchKey}>Match</EntityLink>}</article>)}</div></section>:null}
  </>}
 </div>;
}
