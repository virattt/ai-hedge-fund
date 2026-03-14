import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { AppNavbar } from './components/navigation/app-navbar';
import { Toaster } from './components/ui/sonner';
import { HomePage } from './pages/home-page';
import { ScrapingResultsPage } from './pages/scraping-results-page';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex flex-col h-screen">
        <AppNavbar />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/editor" element={<Layout />} />
          <Route path="/scraping" element={<ScrapingResultsPage />} />
        </Routes>
      </div>
      <Toaster />
    </BrowserRouter>
  );
}
