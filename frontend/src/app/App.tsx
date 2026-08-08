import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { MatchDetailPage } from '../pages/MatchDetailPage';
import { OverviewPage } from '../pages/OverviewPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/oversikt" replace />} />
        <Route path="/oversikt" element={<OverviewPage />} />
        <Route path="/auto" element={<PlaceholderPage title="Auto" />} />
        <Route path="/watchlist" element={<PlaceholderPage title="Watchlist" />} />
        <Route path="/resultatloop" element={<PlaceholderPage title="Resultatloop" />} />
        <Route path="/historik" element={<PlaceholderPage title="Historik" />} />
        <Route path="/matcher/:matchId" element={<MatchDetailPage />} />
        <Route path="/lag/:teamId" element={<PlaceholderPage title="Lagstatistik" />} />
        <Route path="/modell" element={<PlaceholderPage title="Modell & proof" />} />
        <Route path="/systemstatus" element={<PlaceholderPage title="Systemstatus" />} />
        <Route path="*" element={<Navigate to="/oversikt" replace />} />
      </Routes>
    </AppShell>
  );
}
