import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { EntityLink } from '../components/EntityLink';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useTeam } from '../data/queries';
import { flattenContext, strongestDeviations, type Orientation, type ProfileContextKey } from '../domain/team-stats';

function pct(value:number|null){return value===null?'—':`${value>0?'+':''}${value.toLocaleString('sv-SE',{minimumFractionDigits:1,maximumFractionDigits:1})} %`;}
function contextLabel(value:ProfileContextKey){return value==='home'?'Hemma':'Borta';}
function orientationLabel(value:Orientation){return value==='for'?'FOR':'AGAINST';}

export function TeamPage(){
 const{teamId}=useParams();const query=useTeam(teamId);const[contextKey,setContextKey]=useState<ProfileContextKey>('home');const[orientation,setOrientation]=useState<Orientation>('for');const[period,setPeriod]=useState('ALL');
 if(query.isLoading)return <StateNotice state="loading" title="Hämtar lagprofil" detail="Läser lagets statistik och ligaranking."/>;
 if(query.isError||!query.data)return <StateNotice state="empty" title="Lagprofil saknas" detail="Ingen lagprofil kunde hittas."/>;
 const data=query.data;const{team,league,contexts}=data;const availableContext=contexts[contextKey]??contexts.home??contexts.away;const activeKey=(contexts[contextKey]?contextKey:(contexts.home?'home':'away')) as ProfileContextKey;
 const rows=useMemo(()=>flattenContext(availableContext,activeKey).filter((row)=>row.orientation===orientation&&row.period===period),[availableContext,activeKey,orientation,period]);
 const deviations=useMemo(()=>strongestDeviations(data),[data]);
 return <div className="page-stack">
  <PageHeader eyebrow={league?.leagueName??'Lagprofil'} title={team.teamName??team.teamKey} subtitle={[team.optaRank!==null?`Opta #${team.optaRank}`:null,team.optaRating!==null?`Rating ${team.optaRating.toLocaleString('sv-SE')}`:null].filter(Boolean).join(' · ')||'Liga-relativ lagstatistik'} aside={league?<EntityLink kind="league" id={league.leagueKey} className="quiet-link">Öppna ligan</EntityLink>:undefined}/>
  <section className="profile-controls" aria-label="Lagprofilfilter">
   <div className="segmented">{(['home','away'] as const).map((key)=><button type="button" key={key} disabled={!contexts[key]} className={activeKey===key?'is-active':''} onClick={()=>setContextKey(key)} aria-label={key==='home'?'Hemmaprofil':'Bortaprofil'}>{key==='home'?'Hemma':'Borta'}</button>)}</div>
   <div className="segmented">{(['for','against'] as const).map((key)=><button type="button" key={key} className={orientation===key?'is-active':''} onClick={()=>setOrientation(key)} aria-label={orientationLabel(key)}>{orientationLabel(key)}</button>)}</div>
   <div className="segmented">{['ALL','1ST','2ND'].map((key)=><button type="button" key={key} className={period===key?'is-active':''} onClick={()=>setPeriod(key)}>{key}</button>)}</div>
  </section>
  {!availableContext?<StateNotice state="empty" title="Teamprofile-data saknas" detail="Ingen aktuell hemma- eller bortaprofil finns."/>:<>
   <section className="product-section"><div className="section-heading"><div><p className="eyebrow">Liga-relativ profil</p><h2>Största avvikelser mot ligan</h2></div></div><div className="deviation-columns">
    <div><h3>Högst över ligasnitt</h3>{deviations.above.map((row)=><article className="deviation-row" key={`above:${row.context}:${row.orientation}:${row.statKey}:${row.period}`}><div><strong>{row.statKey}</strong><small>{contextLabel(row.context)} · {orientationLabel(row.orientation)} · {row.period}</small></div><span>{row.value.toLocaleString('sv-SE')}</span><b>{pct(row.deviationPct)}</b><em>{row.rank!==null?`#${row.rank}`:'—'}</em></article>)}</div>
    <div><h3>Lägst under ligasnitt</h3>{deviations.below.map((row)=><article className="deviation-row" key={`below:${row.context}:${row.orientation}:${row.statKey}:${row.period}`}><div><strong>{row.statKey}</strong><small>{contextLabel(row.context)} · {orientationLabel(row.orientation)} · {row.period}</small></div><span>{row.value.toLocaleString('sv-SE')}</span><b>{pct(row.deviationPct)}</b><em>{row.rank!==null?`#${row.rank}`:'—'}</em></article>)}</div>
   </div></section>
   <section className="product-section"><div className="section-heading"><div><p className="eyebrow">Stat explorer</p><h2>{contextLabel(activeKey)} · {orientationLabel(orientation)} · {period}</h2></div></div>{rows.length===0?<StateNotice state="empty" title="Ingen statistik i kombinationen" detail="Välj en annan kontext, riktning eller period."/>:<div className="stats-table" role="table"><div className="stats-row stats-row--head" role="row"><span>Stat</span><span>Värde</span><span>Rank</span><span>Ligasnitt</span></div>{rows.map((row)=><div className="stats-row" role="row" key={row.statKey}><strong>{row.statKey}</strong><span>{row.value.toLocaleString('sv-SE')}</span><span>{row.rank!==null?`#${row.rank}`:'—'}</span><span>{row.leagueAverage?.toLocaleString('sv-SE')??'—'}</span></div>)}</div>}</section>
   {availableContext.games.length?<section className="product-section"><div className="section-heading"><div><p className="eyebrow">Historik</p><h2>Matcher i profilen</h2></div></div><div className="entity-list">{availableContext.games.map((game,index)=><article className="entity-row" key={`${game.matchKey??game.matchId??index}`}><time>{game.date??'—'}</time><div className="entity-row__main"><EntityLink kind="team" id={game.opponentTeamKey}>{game.opponentName??'Okänd motståndare'}</EntityLink></div>{game.homeScore!==null&&game.awayScore!==null?<EntityLink kind="match" id={game.matchKey}>{game.homeScore}–{game.awayScore}</EntityLink>:<EntityLink kind="match" id={game.matchKey}>Match</EntityLink>}</article>)}</div></section>:null}
  </>}
 </div>;
}
