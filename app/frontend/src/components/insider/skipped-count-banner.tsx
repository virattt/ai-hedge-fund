/**
 * Banner displayed when some filings could not be parsed by the backend.
 * Renders nothing when `skippedCount` is zero.
 */
export function SkippedCountBanner({
  skippedCount,
  shownCount,
  totalCount,
  itemLabel = 'records',
}: {
  skippedCount: number;
  shownCount: number;
  totalCount: number;
  itemLabel?: string;
}) {
  if (skippedCount <= 0) return null;
  return (
    <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-400">
      Showing {shownCount} of {totalCount} {itemLabel} ({skippedCount} could not be parsed)
    </div>
  );
}
