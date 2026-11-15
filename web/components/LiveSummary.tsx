"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { coveredMonths, livePlan } from "@/lib/plans";
import type { Plan } from "@/lib/types";
import { CoverMeter } from "./CoverMeter";
import styles from "./LiveSummary.module.css";
import { StepList } from "./PlanCard";
import { YearStrip } from "./YearStrip";

function Cover({ label, months }: { label: string; months: number | null }) {
  if (months === null) return null;
  return (
    <div className={styles.cover}>
      <p>
        <span>{label}</span>
        <span className="num">{months} of 12 months</span>
      </p>
      <CoverMeter months={months} />
    </div>
  );
}

/**
 * The option the answers currently point to, kept in view while the farmer edits
 * them: a sticky panel beside the questions, a bottom bar on narrow screens.
 */
export function LiveSummary({
  plans,
  pending,
  error,
  barVisible,
}: {
  plans: Plan[];
  pending: boolean;
  error: string | null;
  barVisible: boolean;
}) {
  const reduce = useReducedMotion();
  const { best, current, shown } = livePlan(plans);
  const fade = reduce
    ? { initial: false as const, transition: { duration: 0 } }
    : {
        initial: { opacity: 0, y: 6 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -4 },
        transition: { duration: 0.2, ease: [0.22, 1, 0.36, 1] as const },
      };
  const status = error ? "Couldn’t update" : pending ? "Updating…" : "Updates as you answer";

  return (
    <>
      <aside className={styles.rail} aria-label="Live result">
        <div className={styles.card}>
          <p className={styles.status} data-state={error ? "error" : pending ? "pending" : "idle"}>
            <span className={styles.dot} aria-hidden="true" />
            {status}
          </p>
          {shown ? (
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={shown.key} {...fade} className={styles.body}>
                <p className={styles.role}>
                  {best ? "Best fit for your priorities" : "Your rotation already fits best"}
                </p>
                <p className={styles.title}>
                  <StepList steps={shown.steps} title={shown.title} />
                </p>
                <div className={styles.strip}>
                  <YearStrip rows={shown.calendar} size="compact" />
                </div>
                {best && current && (
                  <div className={styles.compare}>
                    <Cover label="This option" months={coveredMonths(best.calendar)} />
                    <Cover label="Yours" months={coveredMonths(current.calendar)} />
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          ) : (
            <div className={styles.loading} aria-hidden="true" />
          )}
          <a className={`btn btn-primary ${styles.cta}`} href="#options">
            Compare all options
          </a>
        </div>
      </aside>

      <AnimatePresence>
        {barVisible && shown && (
          <motion.div
            className={styles.bar}
            initial={reduce ? false : { y: "110%" }}
            animate={{ y: 0 }}
            exit={reduce ? { opacity: 0 } : { y: "110%" }}
            transition={reduce ? { duration: 0 } : { duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className={styles.barText} aria-live="polite">
              <p className={styles.barRole}>
                <span className={styles.dot} data-pending={pending || undefined} aria-hidden="true" />
                {best ? "Best fit" : "Your rotation fits best"}
              </p>
              <p className={styles.barTitle}>{shown.steps.join(" → ") || shown.title}</p>
            </div>
            <a className="btn btn-primary" href="#options">
              See options
            </a>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
