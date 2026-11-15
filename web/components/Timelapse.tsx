"use client";

import { useEffect, useState } from "react";
import { PauseIcon, PlayIcon } from "./Icons";
import styles from "./Timelapse.module.css";

interface Layer {
  index: "ndvi" | "rgb";
  label: string;
  available: boolean;
  frames: number;
  size: [number, number] | null;
  message: string | null;
  data_through: string | null;
}

/** Monthly Sentinel-2 composites; month labels are burned into each frame. */
export function Timelapse({ fieldId, layers }: { fieldId: string; layers: Layer[] }) {
  const usable = layers.filter((l) => l.available);
  const [index, setIndex] = useState<Layer["index"]>(usable[0]?.index ?? "ndvi");
  const layer = layers.find((l) => l.index === index);
  const n = layer?.frames ?? 0;
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
    const t = window.setInterval(() => setFrame((f) => (f + 1) % n), 800);
    return () => window.clearInterval(t);
  }, [playing, n]);

  if (!layer || !layer.available) {
    return (
      <div className={styles.empty}>
        <p>{layer?.message ?? "Timelapse not available for this field yet."}</p>
      </div>
    );
  }

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
          alt={`${layer.label}, frame ${frame + 1} of ${n}`}
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
          aria-label="Month frame"
          aria-valuetext={`Frame ${frame + 1} of ${n}`}
        />
        <span className={styles.count}>
          {frame + 1}/{n}
        </span>
      </div>
      <p className="caption">
        Monthly cloud-masked Sentinel-2 composites
        {layer.data_through ? `, data through ${layer.data_through}` : ""}.
      </p>
    </div>
  );
}
