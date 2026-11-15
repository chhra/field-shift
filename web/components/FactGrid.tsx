import type { Fact } from "@/lib/types";
import styles from "./FactGrid.module.css";

export function FactGrid({ facts }: { facts: Fact[] }) {
  return (
    <dl className={styles.grid} data-count={facts.length}>
      {facts.map((f) => (
        <div key={f.label} className={styles.fact}>
          <dt className={styles.label}>{f.label}</dt>
          <dd className={styles.value}>{f.value}</dd>
          <dd className={styles.meaning}>{f.meaning}</dd>
          <dd className={styles.source}>{f.source}</dd>
        </div>
      ))}
    </dl>
  );
}
