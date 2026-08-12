import { ExternalLink } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { EntityLink } from '../components/EntityLink';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { useLeague } from '../data/queries';
import { formatKickoff } from '../domain/formatters';

function pct(value:number,average:number|null){if(average===null||average===0)return '—';const diff=((value-average)/average)*100;return `${diff>0?'+':''}${diff.toLocaleString('sv-SE',{minimumFractionDigits:1,maximumFractionDigits:1})} %`;}

export function LeaguePage(){
 const{leagueId}=useParams();const query=useLeague(leagueId);const[context,setContext]=useState('home');const[orientation,setOrientation]=useState('for');const[period,setPeriod]=useState('ALL');const[stat,setStat]=useState('');
 if(query.isLoading)return <StateNotice state="loading" title="Hämtar liga" detail="Läser liga, lag, matcher och statistikranking."/>;
 if(query.isError||!query.data)return <StateNotice state="failed" title="Ligan kunde inte hämtas" detail="Ligan finns inte eller datakällan kunde inte nås."/>;
 const{league,teams,matches,statRows}=query.data;const statKeys=Array.from(new Set(statRows.map((row)=>row.statKey))).sort((a,b)=>a.localeCompare(b,'sv'));const selectedStat=stat||statKeys[0]||'';
 const ranking=statRows.filter((row)=>row.context===context&&row.orientation===orientation&&row.period===period&&row.statKey===selectedStat).sort((a,b)=>(a.rank??999)-(b.rank??999)||b.value-a.value);
 return <div className="page-stack">
  <PageHeader eyebrow={[league.country,league.seasonId].filter((v)=>v!==null&&v!=='').join(' · ')||'Liga'} title={league.leagueName??'Okänd liga'} subtitle={`${teams.length} lag · ${matches.length} matcher i läsvyn`}/>
  <section className="product-section"><div className="section-heading"><div><p className="eyebrow">Stat explorer</p><h2>Statistikranking</h2></div></div>
   <div className="profile-controls"><select aria-label="Stat" value={selectedStat} onChange={(e)=>setStat(e.target.value)}>{statKeys.map((key)=><option value={key} key={key}>{key}</option>)}</select><div className="segmented">{['home','away'].map((key)=><button type="button" key={key} className={context===key?'is-active':''} onClick={()=>setContext(key)}>{key==='home'?'Hemma':'Borta'}</button>)}</div><div className="segmented">{['for','against'].map((key)=><button type="button" key={key} className={orientation===key?'is-active':''} onClick={()=>setOrientation(key)}>{key.toUpperCase()}</button>)}</div><div className="segmented">{['ALL','1ST','2ND'].map((key)=><button type="button" key={key} className={period===key?'is-active':''} onClick={()=>setPeriod(key)}>{key}</button>)}</div></div>
   {ranking.length===0?<StateNotice state="empty" title="Ingen ranking i kombinationen" detail="Välj en annan stat, kontext eller period."/>:<div className="stats-table" role="table"><div className="stats-row stats-row--head" role="row"><span>Lag</span><span>Värde</span><span>Rank</span><span>Mot ligan</span></div>{ranking.map((row)=><div className="stats-row" role="row" key={`${row.teamKey}:${row.context}:${row.orientation}:${row.statKey}:${row.period}`}><strong><EntityLink kind="team" id={row.teamKey}>{row.teamName}</EntityLink></strong><span>{row.value.toLocaleString('sv-SE')}</span><span>{row.rank!==null?`#${row.rank}`:'—'}</span><span>{pct(row.value,row.leagueAverage)}</span></div>)}</div>}
  </section>
  <section className="product-section"><div className="section-heading"><div><p className="eyebrow">Lag</p><h2>Lag i ligan</h2></div></div>{teams.length===0?<StateNotice state="empty" title="Inga lag hittades" detail="Lagdata saknas för ligan."/>:<div className="entity-grid">{teams.map((team)=><EntityLink kind="team" id={team.teamKey} className="entity-card" key={team.teamKey}><strong>{team.teamName??team.teamKey}</strong>{team.optaRank!==null?<span>Opta #{team.optaRank}</span>:<span>Lagprofil</span>}</EntityLink>)}</div>}</section>
  <section className="product-section"><div className="section-heading"><div><p className="eyebrow">Matcher</p><h2>Matcher</h2></div></div>{matches.length===0?<StateNotice state="empty" title="Inga matcher hittades" detail="Ingen matchdata finns i läsvyn."/>:<div className="entity-list">{matches.map((match)=>{const label=`${match.homeTeamName??'Okänt lag'} – ${match.awayTeamName??'Okänt lag'}`;return <article className="entity-row" key={match.matchKey}><time dateTime={match.startTime??undefined}>{match.startTime?formatKickoff(match.startTime):'Tid saknas'}</time><div className="entity-row__main"><EntityLink kind="team" id={match.homeTeamKey}>{match.homeTeamName??'Okänt lag'}</EntityLink><span> – </span><EntityLink kind="team" id={match.awayTeamKey}>{match.awayTeamName??'Okänt lag'}</EntityLink></div>{match.homeScore!==null&&match.awayScore!==null?<strong>{match.homeScore}–{match.awayScore}</strong>:null}<EntityLink kind="match" id={match.matchKey} className="quiet-link" ariaLabel={`Öppna ${label}`}><ExternalLink size={14}/><span>Match</span></EntityLink></article>;})}</div>}</section>
 </div>;
}
