import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { EntityLink } from '../components/EntityLink';
import { StateNotice } from '../components/StateNotice';
import { TeamCrest } from '../components/TeamCrest';
import { TeamLeagueComparisonChart } from '../components/TeamLeagueComparisonChart';
import { useTeam } from '../data/queries';
import { buildTeamStatChartRows, type ProfileContextKey } from '../domain/team-stats';

export function TeamPage(){
 const{teamId}=useParams();const query=useTeam(teamId);const[contextKey,setContextKey]=useState<ProfileContextKey>('home');
 if(query.isLoading)return <StateNotice state="loading" title="Hämtar lagprofil" detail="Läser lagets statistik och ligaranking."/>;
 if(query.isError||!query.data)return <StateNotice state="empty" title="Lagprofil saknas" detail="Ingen lagprofil kunde hittas."/>;
 const data=query.data;const{team,league,contexts}=data;const availableContext=contexts[contextKey]??contexts.home??contexts.away;const activeKey:ProfileContextKey=contexts[contextKey]?contextKey:contexts.home?'home':'away';
 const forRows=buildTeamStatChartRows(availableContext,activeKey,'for');const againstRows=buildTeamStatChartRows(availableContext,activeKey,'against');
 return <div className="page-stack team-profile-page">
  <header className="team-profile-header">
   <div className="team-profile-header__identity">
    <TeamCrest name={team.teamName} imageUrl={team.teamImageUrl} teamId={team.teamId} teamKey={team.teamKey} size="lg" />
    <div className="team-profile-header__copy">
     {league?<EntityLink kind="league" id={league.leagueKey} className="team-profile-header__league">{league.leagueName??'Liga'}</EntityLink>:<span className="team-profile-header__league">Lagprofil</span>}
     <h1>{team.teamName??team.teamKey}</h1>
     <div className="team-profile-header__meta">
      {team.optaRank!==null?<span>Opta-rank <strong>#{team.optaRank}</strong></span>:null}
      {team.optaRating!==null?<span>Rating <strong>{team.optaRating.toLocaleString('sv-SE')}</strong></span>:null}
     </div>
    </div>
   </div>
   <div className="team-profile-header__controls">
    <div className="team-profile-header__filter">
     <span>Spelplats</span>
     <div className="segmented">{(['home','away'] as const).map((key)=><button type="button" key={key} disabled={!contexts[key]} className={activeKey===key?'is-active':''} onClick={()=>setContextKey(key)} aria-label={key==='home'?'Hemmaprofil':'Bortaprofil'}>{key==='home'?'Hemma':'Borta'}</button>)}</div>
    </div>
    {league?<EntityLink kind="league" id={league.leagueKey} className="team-profile-header__league-link">Öppna ligan</EntityLink>:null}
   </div>
  </header>
  {!availableContext?<StateNotice state="empty" title="Teamprofile-data saknas" detail="Ingen aktuell hemma- eller bortaprofil finns."/>:<>
   <TeamLeagueComparisonChart title={`${team.teamName} · FÖR`} subtitle={`Lagets egna nyckeltal · ${activeKey==='home'?'hemma':'borta'} · totalt, 1:a och 2:a halvlek`} accessibleName="Lagets statistik jämfört med ligan" rows={forRows}/>
   <TeamLeagueComparisonChart title={`${team.teamName} · MOT`} subtitle={`Motståndarnas nyckeltal mot laget · ${activeKey==='home'?'hemma':'borta'} · totalt, 1:a och 2:a halvlek`} accessibleName="Motståndarnas statistik mot laget jämfört med ligan" rows={againstRows}/>
   {availableContext.games.length?<section className="product-section"><div className="section-heading"><div><p className="eyebrow">Historik</p><h2>Matcher i profilen</h2></div></div><div className="entity-list">{availableContext.games.map((game,index)=><article className="entity-row" key={`${game.matchKey??game.matchId??index}`}><time>{game.date??'—'}</time><div className="entity-row__main"><span className="entity-row__team"><TeamCrest name={game.opponentName} teamKey={game.opponentTeamKey} size="xs"/><EntityLink kind="team" id={game.opponentTeamKey}>{game.opponentName??'Okänd motståndare'}</EntityLink></span></div>{game.homeScore!==null&&game.awayScore!==null?<EntityLink kind="match" id={game.matchKey}>{game.homeScore}–{game.awayScore}</EntityLink>:<EntityLink kind="match" id={game.matchKey}>Match</EntityLink>}</article>)}</div></section>:null}
  </>}
 </div>;
}
