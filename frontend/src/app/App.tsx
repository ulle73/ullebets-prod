import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { matchDetailPath, publicMatchId } from '../domain/match-route';
import { OverviewPage } from '../pages/OverviewPage';

const AutoPage = lazy(() => import('../pages/AutoPage').then((module) => ({ default: module.AutoPage })));
const HistoryPage = lazy(() => import('../pages/HistoryPage').then((module) => ({ default: module.HistoryPage })));
const LeaguePage = lazy(() => import('../pages/LeaguePage').then((module) => ({ default: module.LeaguePage })));
const MatchDetailPage = lazy(() => import('../pages/MatchDetailPage').then((module) => ({ default: module.MatchDetailPage })));
const ModelPage = lazy(() => import('../pages/ModelPage').then((module) => ({ default: module.ModelPage })));
const NotFoundPage = lazy(() => import('../pages/NotFoundPage').then((module) => ({ default: module.NotFoundPage })));
const ResultsLoopPage = lazy(() => import('../pages/ResultsLoopPage').then((module) => ({ default: module.ResultsLoopPage })));
const SystemStatusPage = lazy(() => import('../pages/SystemStatusPage').then((module) => ({ default: module.SystemStatusPage })));
const TeamPage = lazy(() => import('../pages/TeamPage').then((module) => ({ default: module.TeamPage })));
const WatchlistPage = lazy(() => import('../pages/WatchlistPage').then((module) => ({ default: module.WatchlistPage })));

function MatchRoute() {
  const { matchId } = useParams();
  if (!matchId) return <Navigate to="/oversikt" replace />;
  const neutralMatchId = publicMatchId(matchId);
  if (neutralMatchId !== matchId) return <Navigate to={matchDetailPath(matchId)} replace />;
  return <MatchDetailPage />;
}

export function App() {
  return (
    <AppShell>
      <Suspense fallback={<div className="route-loading" role="status">Laddar vy</div>}>
        <Routes>
          <Route path="/" element={<Navigate to="/oversikt" replace />} />
          <Route path="/oversikt" element={<OverviewPage />} />
          <Route path="/auto" element={<AutoPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/resultatloop" element={<ResultsLoopPage />} />
          <Route path="/historik" element={<HistoryPage />} />
          <Route path="/matcher/:matchId" element={<MatchRoute />} />
          <Route path="/lag/:teamId" element={<TeamPage />} />
          <Route path="/liga/:leagueId" element={<LeaguePage />} />
          <Route path="/modell" element={<ModelPage />} />
          <Route path="/systemstatus" element={<SystemStatusPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
