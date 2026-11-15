"use client";

import { motion, useReducedMotion } from "motion/react";
import { Fragment } from "react";
import type { Plan, PlanDetails } from "@/lib/types";
import { Disclosure } from "./Disclosure";
import styles from "./PlanCard.module.css";
import { YearStrip } from "./YearStrip";

function Steps({ steps, title }: { steps: string[]; title: string }) {
  if (!steps.length) return <h3 className={styles.title}>{title}</h3>;
  return (
    <h3 className={styles.title} title={title}>
      {steps.map((s, i) => (
        <Fragment key={`${s}-${i}`}>
          {i > 0 && (
            <span className={styles.arrow} aria-label="then">
              {" → "}
            </span>
          )}
          <span className={styles.step}>{s}</span>
        </Fragment>
      ))}
    </h3>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className={styles.detailBlock}>
      <h4>{title}</h4>
      <ul>
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

function Details({ d }: { d: PlanDetails }) {
  return (
    <>
      {d.why && (
        <div className={styles.detailBlock}>
          <h4>Why this option</h4>
          <p>{d.why}</p>
        </div>
      )}
      <List title="Benefits" items={d.benefits} />
      {d.evidence.length > 0 && (
        <div className={styles.detailBlock}>
          <h4>Evidence</h4>
          <ul>
            {d.evidence.map((e, i) => (
              <li key={i}>
                {e.text}
                <span className={styles.source}>
                  {e.source}
                  {e.data_through ? `, data through ${e.data_through}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <List title="Risks" items={d.risks} />
      <List title="Check locally" items={d.checks} />
      <List title="Information gaps" items={d.gaps} />
      {d.confidence && (
        <p className={styles.confidence}>Confidence in this comparison: {d.confidence}</p>
      )}
    </>
  );
}

export function PlanCard({ plan, showDetails = true }: { plan: Plan; showDetails?: boolean }) {
  const reduce = useReducedMotion();
  const cls = [
    styles.plan,
    plan.featured ? styles.featured : "",
    plan.role === "unsuitable" ? styles.muted : "",
  ].join(" ");
  return (
    <motion.article
      layout={reduce ? false : "position"}
      transition={{ type: "spring", stiffness: 380, damping: 36 }}
      className={cls}
      aria-label={`${plan.eyebrow}: ${plan.steps.join(", then ") || plan.title}`}
    >
      <header className={styles.head}>
        <div className={styles.roleRow}>
          <p className={styles.role}>{plan.eyebrow}</p>
          {plan.featured && <span className={styles.badge}>Best for your priorities</span>}
        </div>
        <Steps steps={plan.steps} title={plan.title} />
        {plan.meta && <p className={styles.meta}>{plan.meta}</p>}
      </header>

      {plan.calendar.length > 0 && (
        <div className={styles.calendar}>
          <YearStrip rows={plan.calendar} size="compact" />
        </div>
      )}

      {plan.blurb && <p className={styles.blurb}>{plan.blurb}</p>}

      {plan.flags.length > 0 && (
        <ul className={`${styles.flags} ${plan.flag_tone === "bad" ? styles.bad : ""}`}>
          {plan.flags.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      )}

      <div className={styles.features}>
        <h4>What stands out</h4>
        {plan.features.length ? (
          <ul>
            {plan.features.map((f, i) => (
              <li key={i}>
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    d="M3.5 8.5 6.5 11.5 12.5 4.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.empty}>No standout benefits listed.</p>
        )}
      </div>

      {showDetails && (
        <div className={styles.more}>
          <Disclosure summary="Details and local checks" tone="inline">
            <Details d={plan.details} />
          </Disclosure>
        </div>
      )}
    </motion.article>
  );
}

export function PlanGrid({ plans, showDetails = true }: { plans: Plan[]; showDetails?: boolean }) {
  return (
    <div className={styles.grid} data-count={plans.length}>
      {plans.map((p) => (
        <PlanCard key={p.key} plan={p} showDetails={showDetails} />
      ))}
    </div>
  );
}
