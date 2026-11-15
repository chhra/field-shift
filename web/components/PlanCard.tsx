"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Fragment, useEffect, useRef, useState } from "react";
import { coveredMonths } from "@/lib/plans";
import type { Plan, PlanDetails } from "@/lib/types";
import { CoverMeter, coverDelta } from "./CoverMeter";
import { Disclosure } from "./Disclosure";
import styles from "./PlanCard.module.css";
import { YearStrip } from "./YearStrip";

const SPRING = { type: "spring", stiffness: 380, damping: 36 } as const;

export function StepList({ steps, title }: { steps: string[]; title: string }) {
  if (!steps.length) return <>{title}</>;
  return (
    <>
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
    </>
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

/** What changes against the farmer's rotation, read off the two calendars. */
function SoilCover({ plan, base }: { plan: Plan; base: number | null }) {
  const months = coveredMonths(plan.calendar);
  if (months === null) return <div className={styles.change} />;
  const delta = plan.role === "current" ? null : coverDelta(months, base);
  return (
    <div className={styles.change}>
      <p className={styles.changeHead}>
        <span>
          Soil covered <strong className="num">{months}</strong> of 12 months
        </span>
        {plan.role === "current" ? (
          <span className={styles.delta} data-tone="base">
            Your starting point
          </span>
        ) : (
          delta && (
            <span className={styles.delta} data-tone={delta.tone}>
              {delta.text}
            </span>
          )
        )}
      </p>
      <CoverMeter months={months} />
    </div>
  );
}

export function PlanCard({
  plan,
  base,
  showDetails = true,
  flash = false,
}: {
  plan: Plan;
  base: number | null;
  showDetails?: boolean;
  flash?: boolean;
}) {
  const reduce = useReducedMotion();
  const cls = [
    styles.plan,
    plan.featured ? styles.featured : "",
    plan.role === "unsuitable" ? styles.muted : "",
  ].join(" ");
  return (
    <motion.article
      layout="position"
      initial={reduce ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduce ? { duration: 0 } : { ...SPRING, opacity: { duration: 0.2 } }}
      className={cls}
      data-flash={flash || undefined}
      data-plan={plan.key}
      aria-label={`${plan.eyebrow}: ${plan.steps.join(", then ") || plan.title}`}
    >
      <header className={styles.head}>
        <div className={styles.roleRow}>
          <p className={styles.role}>{plan.eyebrow}</p>
          {plan.featured && <span className={styles.badge}>Best for your priorities</span>}
        </div>
        <h3 className={styles.title} title={plan.title}>
          <StepList steps={plan.steps} title={plan.title} />
        </h3>
        {plan.meta && <p className={styles.meta}>{plan.meta}</p>}
      </header>

      <div className={styles.calendar}>
        {plan.calendar.length > 0 && <YearStrip rows={plan.calendar} size="compact" />}
      </div>

      <SoilCover plan={plan} base={base} />

      <div className={styles.body}>
        {plan.blurb && <p className={styles.blurb}>{plan.blurb}</p>}
        {plan.flags.length > 0 && (
          <ul className={`${styles.flags} ${plan.flag_tone === "bad" ? styles.bad : ""}`}>
            {plan.flags.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        )}
      </div>

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

      <div className={styles.more}>
        {showDetails && (
          <Disclosure summary="Details and local checks" tone="inline">
            <Details d={plan.details} />
          </Disclosure>
        )}
      </div>
    </motion.article>
  );
}

/** Briefly rings the featured card when a changed answer moves the recommendation. */
function useFlash(key: string | undefined) {
  const prev = useRef<string | undefined>(undefined);
  const [flash, setFlash] = useState<string | undefined>(undefined);
  useEffect(() => {
    if (prev.current !== undefined && key && key !== prev.current) {
      setFlash(key);
      const t = window.setTimeout(() => setFlash(undefined), 1400);
      prev.current = key;
      return () => window.clearTimeout(t);
    }
    prev.current = key;
  }, [key]);
  return flash;
}

/**
 * Cards share row tracks (CSS subgrid), so calendars, soil cover and checklists line
 * up across a row. On phones the compare row becomes a swipeable track with a switcher.
 */
export function PlanGrid({
  plans,
  base,
  showDetails = true,
  switcher = false,
}: {
  plans: Plan[];
  base: Plan | null;
  showDetails?: boolean;
  switcher?: boolean;
}) {
  const baseMonths = base ? coveredMonths(base.calendar) : null;
  const flash = useFlash(plans.find((p) => p.featured)?.key);
  const track = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const swipe = switcher && plans.length > 1;

  const onScroll = () => {
    const el = track.current;
    if (!el) return;
    const cards = Array.from(el.children) as HTMLElement[];
    const left = el.scrollLeft + el.clientWidth * 0.3;
    let i = 0;
    cards.forEach((c, k) => {
      if (c.offsetLeft - el.offsetLeft <= left) i = k;
    });
    setActive(i);
  };
  const go = (i: number) => {
    const el = track.current;
    const card = el?.children[i] as HTMLElement | undefined;
    if (!el || !card) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({
      left: card.offsetLeft - el.offsetLeft - parseFloat(getComputedStyle(el).paddingLeft),
      behavior: reduce ? "auto" : "smooth",
    });
  };

  return (
    <div className={styles.wrap}>
      {swipe && (
        <div className={styles.switcher} role="group" aria-label="Show option">
          {plans.map((p, i) => (
            <button
              key={p.key}
              type="button"
              aria-pressed={active === i}
              onClick={() => go(i)}
              className={p.featured ? styles.switchBest : undefined}
            >
              {p.eyebrow}
            </button>
          ))}
        </div>
      )}
      <div
        ref={track}
        className={`${styles.grid} ${swipe ? styles.swipe : ""}`}
        data-count={plans.length}
        onScroll={swipe ? onScroll : undefined}
      >
        <AnimatePresence initial={false}>
          {plans.map((p) => (
            <PlanCard
              key={p.key}
              plan={p}
              base={baseMonths}
              showDetails={showDetails}
              flash={flash === p.key}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
