import type { ReactNode } from "react";
import styles from "./Report.module.css";

/** A numbered report section: the Field and UK pages read top to bottom as steps. */
export function Section({
  id,
  step,
  title,
  lead,
  children,
}: {
  id: string;
  step?: number;
  title: string;
  lead?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className={styles.section} aria-labelledby={`${id}-title`}>
      <header className={styles.sectionHead}>
        {step !== undefined && (
          <span className={styles.step} aria-hidden="true">
            {step}
          </span>
        )}
        <h2 id={`${id}-title`} className={styles.sectionTitle}>
          {step !== undefined && <span className="sr-only">Step {step}: </span>}
          {title}
        </h2>
        {lead && <p className={styles.lead}>{lead}</p>}
      </header>
      {children}
    </section>
  );
}

/** One farmer question: the question is the heading, one reason line under it. */
export function Question({
  n,
  title,
  why,
  children,
  id,
}: {
  n?: number;
  title: string;
  why?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  return (
    <div className={styles.question} role="group" aria-labelledby={id}>
      <div className={styles.qHead}>
        {n !== undefined && (
          <span className={styles.qNum} aria-hidden="true">
            {n}
          </span>
        )}
        <div>
          <h3 id={id} className={styles.qTitle}>
            {title}
          </h3>
          {why && <p className={styles.qWhy}>{why}</p>}
        </div>
      </div>
      <div className={styles.qBody}>{children}</div>
    </div>
  );
}

export function Banner({ children, tone = "good" }: { children: ReactNode; tone?: "good" | "note" }) {
  return (
    <p className={`${styles.banner} ${tone === "note" ? styles.note : ""}`} role="status">
      {children}
    </p>
  );
}

/** Renders the engines' **bold** markup without a markdown dependency. */
export function Rich({ text }: { text: string }) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <>
      {parts.map((p, i) => (i % 2 ? <strong key={i}>{p}</strong> : <span key={i}>{p}</span>))}
    </>
  );
}
