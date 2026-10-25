import { useEffect, useState } from "react";

/** Current time in ms (Date.now), re-rendered every `intervalMs`. Drives live animation. */
export function useTicker(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return now;
}
