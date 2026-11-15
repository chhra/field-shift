import styles from "./CoverMeter.module.css";

/** Twelve cells, one per month: green while the soil is covered, soil-coloured while bare. */
export function CoverMeter({ months }: { months: number }) {
  return (
    <span className={styles.meter} aria-hidden="true">
      {Array.from({ length: 12 }, (_, i) => (
        <i key={i} data-on={i < months} />
      ))}
    </span>
  );
}

export function coverDelta(months: number, base: number | null) {
  if (base === null) return null;
  const d = months - base;
  if (d === 0) return { tone: "same", text: "Same as yours" } as const;
  const n = Math.abs(d);
  return {
    tone: d > 0 ? "up" : "down",
    text: `${d > 0 ? "+" : "−"}${n} ${n === 1 ? "month" : "months"} vs yours`,
  } as const;
}
