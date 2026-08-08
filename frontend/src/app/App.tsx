import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { AutoPage } from '../pages/AutoPage';
import { HistoryPage } from '../pages/HistoryPage';
import { MatchDetailPage } from '../pages/MatchDetailPage';
import { ModelPage } from '../pages/ModelPage';
import { OverviewPage } from '../pages/OverviewPage';
import { ResultsLoopPage } from '../pages/ResultsLoopPage';
import { SystemStatusPage } from '../pages/SystemStatusPage';
import { TeamPage } from '../pages/TeamPage';
import { WatchlistPage } from '../pages/WatchlistPage';

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/oversikt" replace />} />
        <Route path="/oversikt" element={<OverviewPage />} />
        <Route path="/auto" element={<AutoPage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
        <Route path="/resultatloop" element={<ResultsLoopPage />} />
        <Route path="/historik" element={<HistoryPage />} />
        <Route path="/matcher/:matchId" element={<MatchDetailPage />} />
        <Route path="/lag/:teamId" element={<TeamPage />} />
        <Route path="/modell" element={<ModelPage />} />
        <Route path="/systemstatus" element={<SystemStatusPage />} />
        <Route path="*" element={<Navigate to="/oversikt" replace />} />
      </Routes>
    </AppShell>
  );
}
