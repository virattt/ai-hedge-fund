import { Dashboard } from '@/pages/Dashboard';
import { AlertTriangle } from 'lucide-react';

export function BetaLayout() {
  const handleLogout = () => {
    localStorage.removeItem('app_api_key');
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Beta disclaimer banner */}
      <div className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-800 px-4 py-2">
        <div className="max-w-7xl mx-auto flex items-center gap-2 text-xs text-amber-800 dark:text-amber-200">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
          <span>
            <strong>Beta</strong> — Educational tool only. Estimates are experimental and not financial advice.
            Past performance does not guarantee future results.
          </span>
          <button
            onClick={handleLogout}
            className="ml-auto text-xs underline hover:no-underline flex-shrink-0"
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-auto">
        <Dashboard />
      </div>
    </div>
  );
}
