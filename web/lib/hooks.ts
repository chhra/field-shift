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

/**
 * Whether an element is on screen. Returns a callback ref, so it also works for
 * elements that only mount once data has loaded.
 */
export function useOnScreen<T extends Element>(rootMargin = "0px") {
  const [el, setEl] = useState<T | null>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setOn(e.isIntersecting), { rootMargin });
    io.observe(el);
    return () => io.disconnect();
  }, [el, rootMargin]);
  return [setEl, on] as const;
}

/** Matches a media query; false during server render and the first client paint. */
export function useMedia(query: string) {
  const [match, setMatch] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(query);
    setMatch(mq.matches);
    const on = (e: MediaQueryListEvent) => setMatch(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return match;
}
