"use client";

import { useEffect, useState } from "react";
import type { FieldDetail } from "@/lib/types";
import { PauseIcon, PlayIcon } from "./Icons";
import { FULL_MONTHS, MONTHS } from "./YearStrip";
import styles from "./Timelapse.module.css";

type Layer = FieldDetail["timelapse"][number];

/**
 * Monthly Sentinel-2 composites; month labels are burned into each frame. When the
 * frames' months are known the player reports the month on screen (``onMonth``) and
 * jumps to a month asked for from outside (``seek``), which links it to the chart.
 */
export function Timelapse({
  fieldId,
  layers,
  seek = null,
  onMonth,
}: {
  fieldId: string;
  layers: Layer[];
  seek?: number | null;
  onMonth?: (month: number | null) => void;
}) {
  const usable = layers.filter((l) => l.available);
  const [index, setIndex] = useState<Layer["index"]>(usable[0]?.index ?? "ndvi");
  const layer = layers.find((l) => l.index === index);
  const n = layer?.frames ?? 0;
  const months = layer?.months ?? null;
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setPlaying(!reduce);
  }, []);

  useEffect(() => {
    for (let i = 0; i < n; i++) {
      const img = new Image();
      img.src = `/api/fields/${fieldId}/timelapse/${index}/frames/${i}`;
    }
  }, [fieldId, index, n]);

  useEffect(() => {
    if (!playing || n < 2) return;
    const t = window.setInterval(() => setFrame((f) => (f + 1) % n), 900);
    return () => window.clearInterval(t);
  }, [playing, n]);

  useEffect(() => {
    if (seek === null || !months) return;
    const i = months.indexOf(seek);
    if (i < 0) return;
    setPlaying(false);
    setFrame(i);
  }, [seek, months]);

  const month = months?.[frame] ?? null;
  useEffect(() => {
    onMonth?.(month);
  }, [month, onMonth]);

  if (!layer || !layer.available) {
    return (
      <div className={styles.empty}>
        <p>{layer?.message ?? "Timelapse not available for this field yet."}</p>
      </div>
    );
  }

  const where = month ? FULL_MONTHS[month - 1] : `Frame ${frame + 1} of ${n}`;

  return (
    <div className={styles.player}>
      <div className={styles.toggle} role="radiogroup" aria-label="Imagery">
        {usable.map((l) => (
          <button
            key={l.index}
            type="button"
            role="radio"
            aria-checked={l.index === index}
            className={styles.toggleBtn}
            onClick={() => {
              setIndex(l.index);
              setFrame((f) => Math.min(f, l.frames - 1));
            }}
          >
            {l.label}
          </button>
        ))}
      </div>

      <div
        className={styles.screen}
        style={{ aspectRatio: layer.size ? `${layer.size[0]} / ${layer.size[1]}` : undefined }}
      >
        <img
          src={`/api/fields/${fieldId}/timelapse/${index}/frames/${frame}`}
          alt={`${layer.label}, ${where}`}
          width={layer.size?.[0]}
          height={layer.size?.[1]}
        />
      </div>

      <div className={styles.controls}>
        <button
          type="button"
          className={styles.play}
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? "Pause timelapse" : "Play timelapse"}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <input
          type="range"
          min={0}
          max={n - 1}
          value={frame}
          onChange={(e) => {
            setPlaying(false);
            setFrame(Number(e.target.value));
          }}
          className={styles.range}
          aria-label="Month"
          aria-valuetext={where}
        />
        <span className={styles.count}>{month ? MONTHS[month - 1] : `${frame + 1}/${n}`}</span>
      </div>
      <p className="caption">
        Monthly cloud-masked Sentinel-2 composites
        {layer.data_through ? `, data through ${layer.data_through}` : ""}.
      </p>
    </div>
  );
}
