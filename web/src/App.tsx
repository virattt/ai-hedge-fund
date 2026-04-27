import { Routes, Route, Navigate } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { Analyze } from "./screens/Analyze";
import { Backtest } from "./screens/Backtest";
import { History } from "./screens/History";
import { Settings } from "./screens/Settings";
import { Ticker } from "./screens/Ticker";

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <NavBar />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/analyze" element={<Analyze />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/history" element={<History />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/ticker/:symbol" element={<Ticker />} />
          <Route path="*" element={<Navigate to="/analyze" replace />} />
        </Routes>
      </main>
    </div>
  );
}
