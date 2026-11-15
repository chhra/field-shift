"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getJSON, isAbort, postJSON } from "@/lib/api";
import { areaHa, toPolygon } from "@/lib/geo";
import type { GeoJSONPolygon, Square } from "@/lib/types";
import { MapView } from "./map/MapView";
import styles from "./AnalyzeField.module.css";

type Mode = "draw" | "coords";

function useSquare(lat: number, lon: number, size: number) {
  const [square, setSquare] = useState<Square | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const valid =
      Number.isFinite(lat) &&
      Number.isFinite(lon) &&
      Math.abs(lat) <= 90 &&
      Math.abs(lon) <= 180 &&
      size >= 1 &&
      size <= 5000;
    if (!valid) {
      setError("Enter a latitude between −90 and 90, a longitude between −180 and 180, and 1–5000 ha.");
      return;
    }
    const ctrl = new AbortController();
    const t = window.setTimeout(() => {
      getJSON<Square>(`/api/geo/square?lat=${lat}&lon=${lon}&size_ha=${size}`, ctrl.signal)
        .then((s) => {
          setSquare(s);
          setError(null);
        })
        .catch((e) => !isAbort(e) && setError(e.message));
    }, 250);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [lat, lon, size]);
  return { square, error };
}

export function AnalyzeField({ live, statusKnown }: { live: boolean; statusKnown: boolean }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("coords");
  const [lat, setLat] = useState("52.205");
  const [lon, setLon] = useState("0.085");
  const [size, setSize] = useState("25");
  const [points, setPoints] = useState<[number, number][]>([]);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const { square, error: squareError } = useSquare(Number(lat), Number(lon), Number(size));
  const drawnArea = useMemo(() => areaHa(points), [points]);

  useEffect(() => {
    if (!busy) return;
    const t0 = Date.now();
    const t = window.setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 1000);
    return () => window.clearInterval(t);
  }, [busy]);

  const target: GeoJSONPolygon | null =
    mode === "coords" ? (square?.polygon ?? null) : points.length >= 3 ? toPolygon(points) : null;
  const name =
    mode === "coords" ? `Field at ${Number(lat).toFixed(3)}, ${Number(lon).toFixed(3)}` : "Your field";

  const analyze = async () => {
    if (!target) return;
    setBusy(true);
    setElapsed(0);
    setError(null);
    try {
      await postJSON("/api/fields/analyze", { polygon: target, name });
      router.push("/field?id=custom");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed.");
      setBusy(false);
    }
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.modes} role="radiogroup" aria-label="How to locate the field">
        {(
          [
            ["coords", "Enter coordinates"],
            ["draw", "Draw on the map"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={mode === k}
            className={styles.mode}
            onClick={() => setMode(k)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className={styles.grid}>
        <div className={styles.controls}>
          {mode === "coords" ? (
            <>
              <p className={styles.hint}>
                Enter the centre of your field. We draw a square of the size you choose around it.
              </p>
              <div className={styles.inputs}>
                <label>
                  <span className="field-label">Latitude</span>
                  <input
                    className="input num"
                    inputMode="decimal"
                    value={lat}
                    onChange={(e) => setLat(e.target.value)}
                    aria-describedby="lat-help"
                  />
                  <span id="lat-help" className="caption">
                    Degrees north (+) or south (−)
                  </span>
                </label>
                <label>
                  <span className="field-label">Longitude</span>
                  <input
                    className="input num"
                    inputMode="decimal"
                    value={lon}
                    onChange={(e) => setLon(e.target.value)}
                    aria-describedby="lon-help"
                  />
                  <span id="lon-help" className="caption">
                    Degrees east (+) or west (−)
                  </span>
                </label>
                <label>
                  <span className="field-label">Field size (ha)</span>
                  <input
                    className="input num"
                    inputMode="decimal"
                    value={size}
                    onChange={(e) => setSize(e.target.value)}
                  />
                </label>
              </div>
              {squareError ? (
                <p className={styles.error}>{squareError}</p>
              ) : (
                square && (
                  <p className={styles.summary}>
                    Square outline of about <strong className="num">{square.area_ha} ha</strong>.
                    Adjust until it sits on your field.
                  </p>
                )
              )}
              <div className={styles.actions}>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!square?.in_uk || !!squareError}
                  onClick={() => router.push(`/uk?lat=${Number(lat)}&lon=${Number(lon)}`)}
                >
                  Open the UK model here
                </button>
                {square && !square.in_uk && (
                  <p className="caption">
                    The UK model covers UK fields only (about 49.5–61° N, 8.7° W–2.1° E).
                  </p>
                )}
              </div>
            </>
          ) : (
            <>
              <p className={styles.hint}>
                Click the map to place each corner of your field. Three corners or more make an
                outline.
              </p>
              <p className={styles.summary}>
                {points.length === 0
                  ? "No corners yet."
                  : points.length < 3
                    ? `${points.length} ${points.length === 1 ? "corner" : "corners"} placed.`
                    : (
                      <>
                        {points.length} corners, about{" "}
                        <strong className="num">{drawnArea.toFixed(1)} ha</strong>.
                      </>
                    )}
              </p>
              <div className={styles.actions}>
                <button
                  type="button"
                  className="btn"
                  disabled={!points.length}
                  onClick={() => setPoints((p) => p.slice(0, -1))}
                >
                  Undo corner
                </button>
                <button
                  type="button"
                  className="btn btn-quiet"
                  disabled={!points.length}
                  onClick={() => setPoints([])}
                >
                  Clear
                </button>
              </div>
            </>
          )}

          <div className={styles.live}>
            <p className={styles.liveTitle}>
              <i data-live={live} aria-hidden="true" />
              {!statusKnown
                ? "Checking for live NASA data…"
                : live
                  ? "Live NASA data available"
                  : "Live analysis is off in this demo"}
            </p>
            {statusKnown && (
              <p className="caption">
                {live
                  ? "Analysis reads about ten years of Earth Engine and NASA POWER data. It takes about a minute."
                  : "Earth Engine credentials are not configured, so only the demo fields can be opened."}
              </p>
            )}
            <button
              type="button"
              className="btn btn-primary"
              disabled={!live || !target || busy}
              onClick={analyze}
            >
              {busy ? "Analyzing…" : "Analyze this field"}
            </button>
            {busy && (
              <div className={styles.progress} role="status">
                <div className={styles.bar}>
                  <span />
                </div>
                <p className="caption num">
                  Reading NASA data for your field: {elapsed} s of about 60 s
                </p>
              </div>
            )}
            {error && <p className={styles.error}>{error}</p>}
          </div>
        </div>

        <MapView
          className={styles.map}
          center={mode === "coords" ? [Number(lat) || 0, Number(lon) || 0] : [42.0, -93.6]}
          zoom={mode === "coords" ? 14 : 5}
          height={460}
          polygon={mode === "coords" ? (square?.polygon ?? null) : null}
          drawPoints={mode === "draw" ? points : undefined}
          onMapClick={
            mode === "draw" ? (la, lo) => setPoints((p) => [...p, [la, lo]]) : undefined
          }
          label={mode === "coords" ? "Map of your field outline" : "Map for drawing your field"}
        />
      </div>
    </div>
  );
}
