"use client";

import { Reorder, useDragControls, useReducedMotion } from "motion/react";
import { useState } from "react";
import type { Choice, GoalKey } from "@/lib/types";
import { ArrowDown, ArrowUp, CloseIcon, GripIcon, PlusIcon } from "./Icons";
import styles from "./GoalRanker.module.css";

const ORDINAL = ["1st", "2nd", "3rd", "4th", "5th", "6th"];

function Row({
  goal,
  place,
  total,
  onMove,
  onRemove,
}: {
  goal: Choice;
  place: number;
  total: number;
  onMove: (step: number) => void;
  onRemove: () => void;
}) {
  const controls = useDragControls();
  const reduce = useReducedMotion();
  return (
    <Reorder.Item
      value={goal.key}
      as="li"
      className={styles.row}
      dragListener={false}
      dragControls={controls}
      layout="position"
      transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 500, damping: 40 }}
      whileDrag={{ scale: 1.015, boxShadow: "0 12px 28px -14px rgba(35, 39, 31, 0.35)" }}
    >
      <button
        type="button"
        className={styles.grip}
        aria-hidden="true"
        tabIndex={-1}
        onPointerDown={(e) => controls.start(e)}
      >
        <GripIcon />
      </button>
      <span className={styles.place}>{place + 1}</span>
      <i className={styles.dot} style={{ background: `var(--goal-${goal.key})` }} />
      <span className={styles.text}>
        <span className={styles.name}>{goal.label}</span>
        {goal.hint && <span className={styles.hint}>{goal.hint}</span>}
      </span>
      <span className={styles.actions}>
        <button
          type="button"
          className={styles.icon}
          onClick={() => onMove(-1)}
          disabled={place === 0}
          aria-label={`Move “${goal.label}” up`}
        >
          <ArrowUp />
        </button>
        <button
          type="button"
          className={styles.icon}
          onClick={() => onMove(1)}
          disabled={place === total - 1}
          aria-label={`Move “${goal.label}” down`}
        >
          <ArrowDown />
        </button>
        <button
          type="button"
          className={styles.icon}
          onClick={onRemove}
          aria-label={`Remove “${goal.label}”: it doesn't matter to me`}
        >
          <CloseIcon />
        </button>
      </span>
    </Reorder.Item>
  );
}

/** The farmer orders the goals. Places only — never percentages. */
export function GoalRanker({
  goals,
  order,
  onChange,
  emptyNote,
}: {
  goals: Choice[];
  order: GoalKey[];
  onChange: (order: GoalKey[]) => void;
  emptyNote: string;
}) {
  const [announce, setAnnounce] = useState("");
  const byKey = Object.fromEntries(goals.map((g) => [g.key, g])) as Record<GoalKey, Choice>;
  const leftOut = goals.filter((g) => !order.includes(g.key as GoalKey));

  const move = (key: GoalKey, step: number) => {
    const i = order.indexOf(key);
    const j = i + step;
    if (j < 0 || j >= order.length) return;
    const next = [...order];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
    setAnnounce(`${byKey[key].label} is now ${ORDINAL[j]}.`);
  };

  return (
    <div className={styles.wrap}>
      {order.length > 0 ? (
        <Reorder.Group
          axis="y"
          as="ol"
          values={order}
          onReorder={(next) => onChange(next as GoalKey[])}
          className={styles.list}
          aria-label="Your goals, most important first"
        >
          {order.map((key, i) => (
            <Row
              key={key}
              goal={byKey[key]}
              place={i}
              total={order.length}
              onMove={(step) => move(key, step)}
              onRemove={() => {
                onChange(order.filter((k) => k !== key));
                setAnnounce(`${byKey[key].label} removed.`);
              }}
            />
          ))}
        </Reorder.Group>
      ) : (
        <p className={styles.empty}>{emptyNote}</p>
      )}

      {leftOut.length > 0 && (
        <div className={styles.out}>
          <p className={styles.outLabel}>Not in your list. Tap one to add it back.</p>
          <ul className={styles.chips}>
            {leftOut.map((g) => (
              <li key={g.key}>
                <button
                  type="button"
                  className={styles.chip}
                  onClick={() => {
                    onChange([...order, g.key as GoalKey]);
                    setAnnounce(`${g.label} added as ${ORDINAL[order.length]}.`);
                  }}
                >
                  <PlusIcon />
                  {g.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
