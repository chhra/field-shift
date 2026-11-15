"use client";

import { useEffect, useRef, useState } from "react";
import { getJSON, isAbort, postJSON } from "./api";

export function useGet<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!path) return;
    const ctrl = new AbortController();
    setError(null);
    getJSON<T>(path, ctrl.signal)
      .then(setData)
      .catch((e) => !isAbort(e) && setError(e.message));
    return () => ctrl.abort();
  }, [path]);
  return { data, error };
}

/**
 * Re-post whenever ``body`` changes, debounced; stale requests are cancelled so
 * the newest answers always win. The first request goes out immediately.
 */
export function useLivePost<Res>(path: string | null, body: unknown, delay = 220) {
  const [data, setData] = useState<Res | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const loaded = useRef(false);
  const key = body === null || body === undefined ? null : JSON.stringify(body);

  useEffect(() => {
    if (!path || key === null) return;
    const ctrl = new AbortController();
    setPending(true);
    const timer = window.setTimeout(
      () => {
        postJSON<Res>(path, JSON.parse(key), ctrl.signal)
          .then((res) => {
            loaded.current = true;
            setData(res);
            setError(null);
            setPending(false);
          })
          .catch((e) => {
            if (isAbort(e)) return;
            setError(e.message);
            setPending(false);
          });
      },
      loaded.current ? delay : 0,
    );
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
  }, [path, key, delay]);

  return { data, error, pending };
}
