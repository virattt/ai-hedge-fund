import { cn } from '@/lib/utils';
import { BarChart3, BookOpen, Calendar, Compass, Home, History, Newspaper, Settings, Star, UserCheck, Workflow, Zap } from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { NotificationBell } from './notification-bell';

const navItems = [
  { to: '/', label: 'Home', icon: Home },
  { to: '/editor', label: 'Editor', icon: Workflow },
  { to: '/scraping', label: 'Scraping Results', icon: Newspaper },
  { to: '/news', label: 'News', icon: BookOpen },
  { to: '/discovery', label: 'Discovery', icon: Compass },
  { to: '/watchlist', label: 'Watchlist', icon: Star },
  { to: '/calendar', label: 'Calendar', icon: Calendar },
  { to: '/catalysts', label: 'Catalysts', icon: Zap },
  { to: '/screener', label: 'Screener', icon: BarChart3 },
  { to: '/insider', label: 'Insiders', icon: UserCheck },
  { to: '/backtest', label: 'Backtest', icon: History },
];

export function AppNavbar() {
  return (
    <div className="shrink-0">
      <nav className="flex items-center gap-1 bg-card/60 backdrop-blur-md px-4 h-10 border-b border-primary/30">
        <div className="flex items-center gap-2 mr-4">
          <span className="relative inline-flex h-2 w-2 rounded-full bg-primary hud-pulse" aria-hidden />
          <span className="text-sm font-semibold text-foreground tracking-wide">J.A.R.V.I.S.</span>
          <span className="text-[10px] font-data uppercase text-primary/70 tracking-widest">online</span>
        </div>
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors uppercase tracking-wider text-xs',
                isActive
                  ? 'bg-accent text-accent-foreground font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
              )
            }
            end={to === '/'}
          >
            <Icon size={14} />
            {label}
          </NavLink>
        ))}
        <div className="ml-auto flex items-center gap-1">
          <NotificationBell />
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                'inline-flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
              )
            }
          >
            <Settings size={14} />
          </NavLink>
        </div>
      </nav>
      <div className="hud-divider" />
    </div>
  );
}
