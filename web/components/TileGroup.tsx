"use client";

import type { ReactNode } from "react";
import styles from "./TileGroup.module.css";

export interface Tile<K extends string | number> {
  key: K;
  label: string;
  hint?: string | null;
  icon?: ReactNode;
  swatch?: string;
}

/** Answer tiles: native radios (arrow keys work), drawn as large tap targets. */
export function TileGroup<K extends string | number>({
  name,
  legend,
  tiles,
  value,
  onChange,
  size = "regular",
  help,
}: {
  name: string;
  legend: string;
  tiles: Tile<K>[];
  value: K;
  onChange: (key: K) => void;
  size?: "regular" | "compact";
  help?: string;
}) {
  return (
    <fieldset className={`${styles.group} ${styles[size]}`}>
      <legend className="sr-only">{legend}</legend>
      <div className={styles.tiles}>
        {tiles.map((t) => {
          const checked = t.key === value;
          return (
            <label key={String(t.key)} className={styles.tile} data-checked={checked}>
              <input
                type="radio"
                name={name}
                value={String(t.key)}
                checked={checked}
                onChange={() => onChange(t.key)}
                className={styles.input}
              />
              {t.icon && <span className={styles.icon}>{t.icon}</span>}
              {t.swatch && <span className={styles.swatch} style={{ background: t.swatch }} />}
              <span className={styles.text}>
                <span className={styles.label}>{t.label}</span>
                {t.hint && <span className={styles.hint}>{t.hint}</span>}
              </span>
            </label>
          );
        })}
      </div>
      {help && <p className={`caption ${styles.help}`}>{help}</p>}
    </fieldset>
  );
}
