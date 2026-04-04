import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { AppNavbar } from './components/navigation/app-navbar';
import { Toaster } from './components/ui/sonner';
import { HomePage } from './pages/home-page';
import { NewsPage } from './pages/news-page';
import { ScrapingResultsPage } from './pages/scraping-results-page';
import { ScreenerPage } from './pages/screener-page';
import { InsiderPage } from './pages/insider-page';
import { InsiderOwnershipPage } from './pages/insider-ownership-page';
import { InsiderGrantsPage } from './pages/insider-grants-page';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex flex-col h-screen">
        <AppNavbar />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/editor" element={<Layout />} />
          <Route path="/scraping" element={<ScrapingResultsPage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/screener" element={<ScreenerPage />} />
          <Route path="/insider" element={<InsiderPage />} />
          <Route path="/insider/ownership" element={<InsiderOwnershipPage />} />
          <Route path="/insider/grants" element={<InsiderGrantsPage />} />
        </Routes>
      </div>
      <Toaster />
    </BrowserRouter>
  );
}
