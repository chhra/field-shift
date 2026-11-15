"use client";

import type { ReactNode } from "react";
import type { Choice, CropChoice, Plan, SoilKey, WaterKey } from "@/lib/types";
import { SOIL_SWATCH, ThermoIcon, WATER_ICONS } from "./Icons";
import { PlanGrid } from "./PlanCard";
import { Banner } from "./Report";
import { Disclosure } from "./Disclosure";
import { TileGroup } from "./TileGroup";
import styles from "./FarmInputs.module.css";

const COUNTS = [1, 2, 3, 4, 5, 6];

/** How many crops, then one picker per crop, in the order they are grown. */
export function CropSlots({
  scope,
  crops,
  choices,
  onCount,
  onPick,
  children,
}: {
  scope: string;
  crops: string[];
  choices: CropChoice[];
  onCount: (n: number) => void;
  onPick: (slot: number, id: string) => void;
  children?: ReactNode;
}) {
  return (
    <div className={styles.slots}>
      <p className={styles.sub} id={`${scope}-count`}>
        How many crops are in your rotation?
      </p>
      <TileGroup
        name={`${scope}-count`}
        legend="How many crops are in your rotation?"
        size="compact"
        tiles={COUNTS.map((n) => ({ key: n, label: String(n) }))}
        value={crops.length}
        onChange={onCount}
        help="Count each main crop once, in the order you grow them. Leave cover crops out."
      />
      <div className={styles.slotGrid}>
        {crops.map((crop, i) => (
          <label key={i} className={styles.slot}>
            <span className="field-label">Crop {i + 1}</span>
            <select
              className="select"
              value={crop}
              onChange={(e) => onPick(i, e.target.value)}
            >
              {!choices.some((c) => c.id === crop) && <option value={crop}>{crop}</option>}
              {choices.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      {children}
    </div>
  );
}

export function WaterTiles({
  scope,
  choices,
  value,
  help,
  onChange,
}: {
  scope: string;
  choices: Choice[];
  value: WaterKey;
  help: string;
  onChange: (k: WaterKey) => void;
}) {
  return (
    <TileGroup
      name={`${scope}-water`}
      legend="Water source"
      tiles={choices.map((c) => {
        const Icon = WATER_ICONS[c.key];
        return { key: c.key as WaterKey, label: c.label, icon: Icon ? <Icon /> : undefined };
      })}
      value={value}
      onChange={onChange}
      help={help}
    />
  );
}

export function SoilTiles({
  scope,
  choices,
  value,
  help,
  onChange,
}: {
  scope: string;
  choices: Choice[];
  value: SoilKey;
  help: string;
  onChange: (k: SoilKey) => void;
}) {
  return (
    <TileGroup
      name={`${scope}-soil`}
      legend="Soil type"
      tiles={choices.map((c) => ({
        key: c.key as SoilKey,
        label: c.label,
        hint: c.hint,
        swatch: SOIL_SWATCH[c.key],
      }))}
      value={value}
      onChange={onChange}
      help={help}
    />
  );
}

export const RAIN_OPTIONS = [
  { key: 0.8, label: "Drier", hint: "20% less rain" },
  { key: 1.0, label: "As now" },
  { key: 1.2, label: "Wetter", hint: "20% more rain" },
];

export const WARMING_OPTIONS = [
  { key: 0, label: "As now" },
  { key: 1, label: "+1 °C", icon: <ThermoIcon /> },
  { key: 2, label: "+2 °C", icon: <ThermoIcon /> },
];

export function WarmingTiles({
  scope,
  value,
  onChange,
}: {
  scope: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <p className={styles.sub}>If seasons ran warmer</p>
      <TileGroup
        name={`${scope}-warming`}
        legend="If seasons ran warmer"
        tiles={WARMING_OPTIONS}
        value={value}
        onChange={onChange}
        help="Example: +2 °C means warmer seasons on top of today’s climate."
      />
    </div>
  );
}

/** Recommendation line, the compare row, more options, and the set-aside ones. */
export function OptionsPanel({
  recommendation,
  note,
  compare,
  others = [],
  unsuitable = [],
  pending,
  error,
}: {
  recommendation: string | null;
  note: string | null;
  compare: Plan[];
  others?: Plan[];
  unsuitable?: Plan[];
  pending: boolean;
  error: string | null;
}) {
  return (
    <div className={styles.options} aria-busy={pending} data-pending={pending}>
      <p className={styles.status} role="status">
        {pending ? "Updating your options…" : ""}
      </p>
      {error && <Banner tone="note">{error}</Banner>}
      {recommendation && <Banner>{recommendation}</Banner>}
      {note && <Banner tone="note">{note}</Banner>}
      {compare.length > 0 && (
        <>
          <h3 className={styles.groupTitle}>Compare your options</h3>
          <PlanGrid plans={compare} />
        </>
      )}
      {others.length > 0 && (
        <>
          <h3 className={styles.groupTitle}>Other options worth considering</h3>
          <PlanGrid plans={others} />
        </>
      )}
      {unsuitable.length > 0 && (
        <div className={styles.setAside}>
          <Disclosure summary={`Show options we don't recommend (${unsuitable.length})`}>
            <p className={styles.setAsideNote}>
              These fail a hard farm constraint or look clearly weaker than your current rotation
              for your priorities.
            </p>
            <PlanGrid plans={unsuitable} showDetails={false} />
          </Disclosure>
        </div>
      )}
    </div>
  );
}
