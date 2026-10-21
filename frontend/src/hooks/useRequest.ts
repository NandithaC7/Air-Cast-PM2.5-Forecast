import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import type { RequestState } from "../types";

export function useRequest<T>(
  load: () => Promise<T>,
  deps: readonly unknown[],
  enabled = true,
): { state: RequestState<T>; reload: () => void } {
  const [state, setState] = useState<RequestState<T>>(enabled ? { status: "loading" } : { status: "idle" });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  const depKey = JSON.stringify(deps);

  useEffect(() => {
    if (!enabled) {
      setState({ status: "idle" });
      return;
    }
    let cancelled = false;
    setState({ status: "loading" });
    loadRef.current().then(
      (data) => {
        if (!cancelled) setState({ status: "ready", data });
      },
      (error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError) {
          if (error.kind === "not_configured") setState({ status: "not_configured", message: error.message });
          else if (error.kind === "not_connected") setState({ status: "not_connected", message: error.message });
          else setState({ status: "error", message: error.message });
          return;
        }
        setState({ status: "error", message: "The request failed before a response could be read." });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [enabled, tick, depKey]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { state, reload };
}
