import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { AppNavbar } from './components/navigation/app-navbar';
import { Toaster } from './components/ui/sonner';
import { SettingsProvider } from './contexts/settings-context';
import { WatchlistProvider } from './contexts/watchlist-context';
import { HomePage } from './pages/home-page';
import { NewsPage } from './pages/news-page';
import { CatalystsPage } from './pages/catalysts-page';
import { ScrapingResultsPage } from './pages/scraping-results-page';
import { ScreenerPage } from './pages/screener-page';
import { SettingsPage } from './pages/settings-page';
import { WatchlistPage } from './pages/watchlist-page';
import { CalendarPage } from './pages/calendar-page';
import { DiscoveryPage } from './pages/discovery-page';
import { TickerDetailPage } from './pages/ticker-detail-page';
import { InsiderPage } from './pages/insider-page';
import { InsiderOpeninsiderPage } from './pages/insider-openinsider-page';
import { InsiderFinnhubPage } from './pages/insider-finnhub-page';
import { InsiderPoliticalPage } from './pages/insider-political-page';
import { InsiderEarningsPage } from './pages/insider-earnings-page';
import { BacktestPage } from './pages/backtest-page';

export default function App() {
  return (
    <BrowserRouter>
      <SettingsProvider>
        <WatchlistProvider>
          <div className="flex flex-col h-screen">
            <AppNavbar />
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/editor" element={<Layout />} />
              <Route path="/scraping" element={<ScrapingResultsPage />} />
              <Route path="/news" element={<NewsPage />} />
              <Route path="/watchlist" element={<WatchlistPage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/discovery" element={<DiscoveryPage />} />
              <Route path="/ticker/:ticker" element={<TickerDetailPage />} />
              <Route path="/catalysts" element={<CatalystsPage />} />
              <Route path="/screener" element={<ScreenerPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/insider" element={<InsiderPage />} />
              <Route path="/insider/openinsider" element={<InsiderOpeninsiderPage />} />
              <Route path="/insider/finnhub" element={<InsiderFinnhubPage />} />
              <Route path="/insider/political" element={<InsiderPoliticalPage />} />
              <Route path="/insider/earnings" element={<InsiderEarningsPage />} />
              <Route path="/backtest" element={<BacktestPage />} />
            </Routes>
          </div>
          <Toaster />
        </WatchlistProvider>
      </SettingsProvider>
    </BrowserRouter>
  );
}
