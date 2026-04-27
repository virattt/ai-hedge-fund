import { Routes, Route, Navigate } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { Analyze } from "./screens/Analyze";
import { History } from "./screens/History";

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <NavBar />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/analyze" element={<Analyze />} />
          <Route path="/history" element={<History />} />
          <Route path="*" element={<Navigate to="/analyze" replace />} />
        </Routes>
      </main>
    </div>
  );
}
