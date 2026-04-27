import { Link, useLocation } from "react-router-dom";
import { BarChart3, History as HistoryIcon } from "lucide-react";
import { cn } from "../lib/utils";

const links = [
  { to: "/analyze", label: "Analyze", icon: BarChart3 },
  { to: "/history", label: "History", icon: HistoryIcon },
] as const;

export function NavBar() {
  const location = useLocation();

  return (
    <nav className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <span className="text-lg font-semibold tracking-tight text-foreground">
          AI Hedge Fund
        </span>
        <div className="flex gap-1">
          {links.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                location.pathname === to
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
