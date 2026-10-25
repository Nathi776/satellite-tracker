import { useEffect, useState } from "react";

export type Polled<T> = {
  data: T | null;
  /** Date.now() when `data` arrived: the moment its rates are measured from */
  receivedAt: number | null;
  error: string | null;
};

const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

/**
 * Calls `fetcher` now and then every `intervalMs`.
 *
 *  - pass `null` to switch polling off
 *  - polling pauses while the tab is hidden and refreshes as soon as it is shown again
 *  - changing `fetcher` (wrap it in useCallback) cancels the request in flight and restarts
 *  - the previous data stays on screen until the new data arrives, so typing in a
 *    search box doesn't make the map flicker
 */
export function usePolling<T>(
  fetcher: ((signal: AbortSignal) => Promise<T>) | null,
  intervalMs: number,
): Polled<T> {
  const [state, setState] = useState<Polled<T>>({ data: null, receivedAt: null, error: null });

  useEffect(() => {
    if (!fetcher) return;

    let controller: AbortController | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const run = async () => {
      controller = new AbortController();
      try {
        const data = await fetcher(controller.signal);
        if (!stopped) setState({ data, receivedAt: Date.now(), error: null });
      } catch (e) {
        if (isAbort(e) || stopped) return;
        setState(prev => ({ ...prev, error: e instanceof Error ? e.message : String(e) }));
      }
      if (!stopped && !document.hidden) timer = setTimeout(run, intervalMs);
    };

    const onVisibility = () => {
      if (document.hidden) {
        clearTimeout(timer);
        controller?.abort();
      } else {
        clearTimeout(timer);
        run();
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    if (!document.hidden) run();

    return () => {
      stopped = true;
      clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [fetcher, intervalMs]);

  return state;
}
