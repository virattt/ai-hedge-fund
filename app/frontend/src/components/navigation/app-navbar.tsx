import { cn } from '@/lib/utils';
import { Home, Newspaper, Workflow } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Home', icon: Home },
  { to: '/editor', label: 'Editor', icon: Workflow },
  { to: '/scraping', label: 'Scraping Results', icon: Newspaper },
];

export function AppNavbar() {
  return (
    <nav className="flex items-center gap-1 border-b border-border bg-background px-4 h-10 shrink-0">
      <span className="text-sm font-semibold text-foreground mr-4">AI Hedge Fund</span>
      {navItems.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
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
    </nav>
  );
}
