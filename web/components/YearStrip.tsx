import type { CSSProperties } from "react";
import type { CalendarRow, CalendarSegment } from "@/lib/types";
import styles from "./YearStrip.module.css";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

type Size = "hero" | "regular" | "compact";

function segmentText(seg: CalendarSegment, size: Size) {
  if (!seg.crop_id) return size !== "compact" && seg.span >= 2 ? "bare" : "";
  if (seg.span === 1 && size === "compact") return "";
  return seg.name + (seg.cover && size === "hero" ? " cover" : "");
}

export function YearStrip({
  rows,
  size = "regular",
  legend = false,
  animate = false,
}: {
  rows: CalendarRow[];
  size?: Size;
  legend?: boolean;
  animate?: boolean;
}) {
  if (!rows.length) return null;
  const labelled = rows.some((r) => r.label);
  return (
    <div
      className={`${styles.strip} ${styles[size]} ${labelled ? styles.labelled : ""} ${
        animate ? styles.animate : ""
      }`}
    >
      <div className={styles.row} aria-hidden="true">
        {labelled && <span className={styles.lab} />}
        <div className={`${styles.track} ${styles.head}`}>
          {MONTHS.map((m) => (
            <span key={m}>{size === "compact" ? m[0] : m}</span>
          ))}
        </div>
      </div>
      {rows.map((row, y) => (
        <div className={styles.row} key={y} role="img" aria-label={row.summary}>
          {labelled && <span className={styles.lab}>{row.label}</span>}
          <div className={styles.track}>
            {row.segments.map((seg, i) => (
              <div
                key={`${seg.start}-${i}`}
                className={`${styles.seg} ${seg.crop_id ? "" : styles.bare} ${
                  seg.cover ? styles.cover : ""
                }`}
                style={
                  {
                    gridColumn: `${seg.start} / span ${seg.span}`,
                    "--tone": `var(--tone-${seg.tone})`,
                    "--i": y * 4 + i,
                  } as CSSProperties
                }
                title={seg.title}
              >
                <span>{segmentText(seg, size)}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
      {legend && <YearLegend />}
    </div>
  );
}

export function YearLegend() {
  return (
    <ul className={styles.legend}>
      <li>
        <i style={{ background: "var(--tone-poaceae)" }} />
        Cereals
      </li>
      <li>
        <i style={{ background: "var(--tone-fabaceae)" }} />
        Legumes
      </li>
      <li>
        <i style={{ background: "var(--tone-brassicaceae)" }} />
        Brassicas
      </li>
      <li>
        <i className={styles.cover} style={{ "--tone": "var(--tone-cover)" } as CSSProperties} />
        Cover crop
      </li>
      <li>
        <i className={styles.bare} />
        Bare soil
      </li>
    </ul>
  );
}
