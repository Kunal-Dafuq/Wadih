import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from './api';

export type AsyncState<T> =
  | { status: 'loading'; data?: undefined; error?: undefined }
  | { status: 'success'; data: T; error?: undefined }
  | { status: 'error'; data?: undefined; error: ApiError };

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'INTERNAL_ERROR', 'Something went wrong.');
}

/** Loads data on mount / when deps change; `reload` re-runs it. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' });
  const seq = useRef(0);
  const run = useCallback(fn, deps);

  const load = useCallback(
    (quiet = false) => {
      const id = ++seq.current;
      if (!quiet) setState({ status: 'loading' });
      run()
        .then((data) => id === seq.current && setState({ status: 'success', data }))
        .catch((e) => id === seq.current && setState({ status: 'error', error: toApiError(e) }));
    },
    [run],
  );

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: () => load(true) } as AsyncState<T> & { reload: () => void };
}

/** Tracks a user-triggered mutation (button press). */
export function useAction<A extends unknown[], T>(fn: (...args: A) => Promise<T>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const run = useCallback(
    async (...args: A): Promise<T | undefined> => {
      setPending(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (e) {
        setError(toApiError(e));
        return undefined;
      } finally {
        setPending(false);
      }
    },
    [fn],
  );
  return { run, pending, error, clearError: () => setError(null) };
}
