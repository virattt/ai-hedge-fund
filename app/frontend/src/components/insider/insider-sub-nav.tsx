import { Link, useLocation } from 'react-router-dom';

/**
 * A navigation link styled for the insider sub-navigation bar.
 * Highlights the active route using `useLocation`.
 */
export function SubNavLink({ to, label }: { to: string; label: string }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link
      to={to}
      className={`text-sm px-3 py-1 rounded-md transition-colors ${
        isActive
          ? 'bg-accent text-accent-foreground font-medium'
          : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
      }`}
    >
      {label}
    </Link>
  );
}
