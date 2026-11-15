"use client";

import type { ReactNode } from "react";
import { useMedia } from "@/lib/hooks";
import type { MapProps } from "./map/LeafletMap";
import { MapView } from "./map/MapView";
import styles from "./SatelliteBand.module.css";

type BandMap = Omit<
  MapProps,
  "height" | "fitPadding" | "nudge" | "zoomPosition" | "attributionPosition"
>;

/** Full-bleed satellite picture of the field with the report's title sheet laid over it. */
export function SatelliteBand({ map, children }: { map: BandMap; children: ReactNode }) {
  const narrow = useMedia("(max-width: 640px)");
  const overlap = narrow ? 48 : 120;
  return (
    <div className={styles.band}>
      <div className={styles.imagery}>
        <MapView
          {...map}
          height="100%"
          flush
          zoomPosition="topright"
          attributionPosition="topright"
          fitPadding={{ top: 24, bottom: overlap + 24, left: 24, right: 72 }}
          nudge={[0, Math.round(overlap / 2)]}
        />
      </div>
      <header className={`page ${styles.sheetWrap}`}>
        <div className={styles.sheet}>{children}</div>
      </header>
    </div>
  );
}

export function Contents({ items }: { items: readonly (readonly [string, string])[] }) {
  return (
    <nav aria-label="On this page" className={styles.contents}>
      <ol>
        {items.map(([id, label], i) => (
          <li key={id}>
            <a href={`#${id}`}>
              <span className="num">{i + 1}</span>
              {label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
