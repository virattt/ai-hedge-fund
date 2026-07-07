import { useEffect, useState } from 'react';

import { getConfiguredProviders } from '@/data/models';

/**
 * Fetches (once, cached) the list of provider names that have an API key configured on
 * the backend via environment variables. Used to gray out models whose provider has no
 * key and to warn when nothing is configured.
 *
 * `providers` is null while loading, and stays null if the status fetch fails, so callers
 * treat "unknown" the same as loading and fail open (enable all models) rather than graying
 * everything out on a transient backend blip. Runs still enforce keys server-side.
 */
export function useConfiguredProviders() {
  const [providers, setProviders] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getConfiguredProviders()
      .then((result) => {
        if (!cancelled) {
          setProviders(result);
        }
      })
      .catch((error) => {
        // Leave providers null (unknown) so the selector fails open.
        console.error('Failed to fetch configured providers:', error);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { providers, loading };
}
