import { BarChart3, Home, Medal } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { MetricTile } from '../components/MetricTile';
import { PageHeader } from '../components/PageHeader';
import { StateNotice } from '../components/StateNotice';
import { teamProfileFixture } from '../data/product-snapshots';

export function TeamPage() {
  const { teamId } = useParams();
  if (teamId !== teamProfileFixture.slug) {
    return (
      <div className="page-stack">
        <PageHeader eyebrow="Teamprofiles" title="Lagstatistik" subtitle="Sidan vägrar fylla en okänd lagprofil med exempelvärden." />
        <StateNotice state="empty" title="Verifierad teamprofile saknas för detta preview-id" detail="Style-1 visar bara den backend-testfixture som är exakt mappad i datainventeringen." />
      </div>
    );
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow={teamProfileFixture.leagueName} title={teamProfileFixture.teamName} subtitle="Verifierad testfixture från backendens teamprofile-kontrakt — inte en live teamprofil." aside={<span className="source-chip">Verifierad testfixture</span>} />
      <div className="metric-tile-grid metric-tile-grid--3">
        <MetricTile label="Hörnor · Match · For" value={teamProfileFixture.cornerAll.value.toLocaleString('sv-SE', { minimumFractionDigits: 1 })} detail="Home profile" tone="brand" icon={<Home size={14} />} />
        <MetricTile label="Ligaposition på stat" value={`Rank ${teamProfileFixture.cornerAll.rank}`} detail="Backend-testens rankfält" icon={<Medal size={14} />} />
        <MetricTile label="Ligasnitt" value="Saknas" detail="Inte verifierat i denna fixture" icon={<BarChart3 size={14} />} />
      </div>
      <section className="product-section">
        <div className="section-heading"><div><p className="eyebrow">Testkontrakt</p><h2>Jämförelse i samma fixture</h2></div><span className="muted-label">Profil-datum {teamProfileFixture.profileDate}</span></div>
        <div className="comparison-row"><div><span>{teamProfileFixture.teamName}</span><strong>{teamProfileFixture.cornerAll.value.toLocaleString('sv-SE', { minimumFractionDigits: 1 })}</strong><small>Hörnor · for · ALL</small></div><div><span>{teamProfileFixture.comparisonTeam.teamName}</span><strong>{teamProfileFixture.comparisonTeam.value.toLocaleString('sv-SE', { minimumFractionDigits: 1 })}</strong><small>Hörnor · for · ALL</small></div></div>
      </section>
    </div>
  );
}
