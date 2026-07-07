import { useEffect, useState } from 'react';

import { getConfiguredProviders } from '@/data/models';

/**
 * Fetches (once, cached) the list of provider names that have an API key configured on
 * the backend via environment variables. Used to gray out models whose provider has no
 * key and to warn when nothing is configured.
 *
 * `providers` is null while loading so callers can avoid graying everything prematurely.
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
