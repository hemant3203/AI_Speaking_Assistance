/**
 * Small data-loading hook: loading, error, reload.
 *
 * A refetch keeps the previous data on screen (`refreshing`) instead of flashing a skeleton, and
 * stale responses are dropped so a slow old request cannot overwrite a newer one.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export function useApi(fetcher, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true, refreshing: false });
  const requestId = useRef(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback(async () => {
    const id = ++requestId.current;
    setState((prev) => ({ ...prev, error: null, loading: prev.data === null, refreshing: prev.data !== null }));
    try {
      const data = await fetcherRef.current();
      if (id === requestId.current) setState({ data, error: null, loading: false, refreshing: false });
      return data;
    } catch (error) {
      if (id === requestId.current) setState((prev) => ({ ...prev, error, loading: false, refreshing: false }));
      return null;
    }
  }, []);

  useEffect(() => {
    load();
    return () => {
      // Invalidate the in-flight request so an unmounted or re-keyed view ignores its response.
      requestId.current += 1;
    };
    // The caller controls refetching through deps, exactly like useEffect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const setData = useCallback((updater) => {
    setState((prev) => ({ ...prev, data: typeof updater === 'function' ? updater(prev.data) : updater }));
  }, []);

  return { ...state, reload: load, setData };
}
