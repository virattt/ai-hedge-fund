import { cn } from '@/lib/utils';

interface ActionBadgeProps {
  label: string;
}

const colorMap: Record<string, string> = {
  'HOLD': 'bg-green-100 text-green-800 border-green-300 dark:bg-green-950 dark:text-green-200 dark:border-green-700',
  'WATCH': 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-700',
  'REVIEW': 'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-950 dark:text-orange-200 dark:border-orange-700',
  'ADD CAUTIOUSLY': 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-200 dark:border-blue-700',
  'REDUCE / REVIEW EXIT': 'bg-red-100 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-700',
};

export function ActionBadge({ label }: ActionBadgeProps) {
  const colors = colorMap[label] || 'bg-muted text-muted-foreground border-border';
  return (
    <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-semibold border shadow-sm', colors)}>
      {label}
    </span>
  );
}
