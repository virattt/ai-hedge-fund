/**
 * Shared number/value/price formatting utilities for the insider trading pages.
 */

/**
 * Format an integer count with locale-based thousands separators.
 * Returns `'—'` for null or undefined.
 */
export const formatNumber = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
};

/**
 * Format a dollar value with compact notation (B / M / K) for large numbers.
 * Returns `'—'` for null or undefined.
 */
export const formatValue = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

/**
 * Format a price with a leading `$` and two decimal places.
 * Returns `'—'` for null or undefined.
 */
export const formatPrice = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
