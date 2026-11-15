"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Disclosure } from "@/components/Disclosure";
import { FactGrid } from "@/components/FactGrid";
import {
  CropSlots,
  OptionsPanel,
  RAIN_OPTIONS,
  SoilTiles,
  WarmingTiles,
  WaterTiles,
} from "@/components/FarmInputs";
import { GoalRanker } from "@/components/GoalRanker";
import { MapView } from "@/components/map/MapView";
import { Question, Rich, Section } from "@/components/Report";
import { SeasonChart } from "@/components/SeasonChart";
import { TileGroup } from "@/components/TileGroup";
import { Timelapse } from "@/components/Timelapse";
import { MONTHS, YearStrip } from "@/components/YearStrip";
import { useGet, useLivePost } from "@/lib/hooks";
import type {
  FieldDetail,
  FieldOptions,
  FieldOptionsRequest,
  GoalKey,
  InputsMeta,
  MonthPick,
  SoilKey,
  WaterKey,
} from "@/lib/types";
import styles from "./FieldReport.module.css";

const CONTENTS = [
  ["field", "Your field"],
  ["satellites", "What the satellites see"],
  ["farm", "About your farm"],
  ["weather", "What if the weather changes?"],
  ["options", "Your options"],
  ["reliability", "How reliable is this?"],
] as const;

interface Answers {
  crops: string[];
  cover: string | null;
  months: (MonthPick | null)[];
  water: WaterKey;
  soil: SoilKey;
  goals: GoalKey[];
  rain: number;
  temp: number;
}

export function FieldReport({ fieldId }: { fieldId: string }) {
  const detail = useGet<FieldDetail>(`/api/fields/${fieldId}`);
  const meta = useGet<InputsMeta>("/api/meta/inputs");
  const [answers, setAnswers] = useState<Answers | null>(null);

  useEffect(() => {
    const s = detail.data?.setup;
    if (!s) return;
    setAnswers({
      crops: s.crops,
      cover: s.cover,
      months: s.crops.map(() => null),
      water: s.water,
      soil: s.soil,
      goals: s.goal_order,
      rain: 1,
      temp: 0,
    });
  }, [detail.data]);

  const body: FieldOptionsRequest | null = useMemo(
    () =>
      answers && {
        crops: answers.crops,
        cover: answers.cover,
        months: answers.months,
        water: answers.water,
        soil: answers.soil,
        goal_order: answers.goals,
        rain_mult: answers.rain,
        temp_offset: answers.temp,
      },
    [answers],
  );
  const options = useLivePost<FieldOptions>(`/api/fields/${fieldId}/options`, body);

  if (detail.error) {
    return (
      <div className={`page ${styles.message}`}>
        <h1>This field report isn’t available</h1>
        <p>{detail.error}</p>
        <Link className="btn btn-primary" href="/">
          Back to Home
        </Link>
      </div>
    );
  }
  if (!detail.data || !meta.data || !answers) return <ReportSkeleton />;

  const d = detail.data;
  const m = meta.data;
  const o = options.data;
  const set = (patch: Partial<Answers>) => setAnswers((a) => (a ? { ...a, ...patch } : a));
  const cashChoices = o?.cash_choices ?? answers.crops.map((id) => ({ id, name: id }));

  const setCount = (n: number) => {
    const ids = cashChoices.map((c) => c.id);
    const fill = [...d.setup.typical_crops, ...ids].filter((c) => ids.includes(c));
    const crops = answers.crops.slice(0, n);
    while (crops.length < n) crops.push(fill.find((c) => !crops.includes(c)) ?? ids[0]);
    set({ crops, months: crops.map((_, i) => answers.months[i] ?? null) });
  };
  const pickCrop = (slot: number, id: string) =>
    set({
      crops: answers.crops.map((c, i) => (i === slot ? id : c)),
      months: answers.months.map((p, i) => (i === slot ? null : p)),
    });
  const pickMonth = (slot: number, key: keyof MonthPick, month: number) => {
    const s = o?.slots[slot];
    if (!s) return;
    const current = answers.months[slot] ?? { plant: s.plant, harvest: s.harvest };
    set({
      months: answers.crops.map((_, i) =>
        i === slot ? { ...current, [key]: month } : (answers.months[i] ?? null),
      ),
    });
  };

  return (
    <article className={styles.report}>
      <header className={`page ${styles.head}`}>
        {d.title && <p className={styles.kicker}>Field report</p>}
        <h1 className={styles.title}>{d.title ?? "Field report"}</h1>
        <dl className={styles.facts}>
          {d.climate_label && (
            <div>
              <dt>Climate</dt>
              <dd>{d.climate_label}</dd>
            </div>
          )}
          {d.area_ha !== null && (
            <div>
              <dt>Area</dt>
              <dd className="num">{Math.round(d.area_ha)} ha</dd>
            </div>
          )}
          {d.season.data_through && (
            <div>
              <dt>Data through</dt>
              <dd>{d.season.data_through}</dd>
            </div>
          )}
        </dl>
        <nav aria-label="On this page" className={styles.contents}>
          <ol>
            {CONTENTS.map(([id, label], i) => (
              <li key={id}>
                <a href={`#${id}`}>
                  <span className="num">{i + 1}</span>
                  {label}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </header>

      <div className="page">
        <Section
          id="field"
          step={1}
          title="Your field"
          lead="Satellite imagery of the outline satellites watch, and a year of monthly Sentinel-2 composites."
        >
          <div className={styles.imagery}>
            <MapView
              center={d.centroid}
              zoom={14}
              height={420}
              polygon={d.polygon}
              label="Satellite map of your field outline"
            />
            <Timelapse fieldId={fieldId} layers={d.timelapse} />
          </div>
        </Section>

        <Section
          id="satellites"
          step={2}
          title="What the satellites see"
          lead="Key facts first, then how a typical year unfolds on this field."
        >
          <FactGrid facts={d.facts} />
          <p className={styles.takeaway}>{d.season.takeaway}</p>
          <SeasonChart
            months={d.season.months}
            bare={d.season.bare_months}
            stress={d.season.stress_months}
          />
          <div className={styles.chartNotes}>
            <Disclosure summary="How to read this chart">
              <p className="prose">
                <Rich text={d.season.how_to_read} />
              </p>
            </Disclosure>
            <Disclosure summary="Stress and unusual seasons">
              <div className="prose">
                {d.anomalies.months.length ? (
                  <ul>
                    {d.anomalies.months.map((a) => (
                      <li key={a.month}>
                        {a.label} was flagged as unusual {a.flags}{" "}
                        {a.flags === 1 ? "time" : "times"} in the record.
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>No growing-season month stands out as repeatedly unusual.</p>
                )}
                {d.anomalies.stress_label && <p>{d.anomalies.stress_label}</p>}
                {d.anomalies.uncertainty && <p>{d.anomalies.uncertainty}</p>}
                <p className="caption">
                  IsolationForest anomaly model
                  {d.anomalies.data_through ? `, data through ${d.anomalies.data_through}` : ""}.
                </p>
              </div>
            </Disclosure>
          </div>
        </Section>

        <Section
          id="farm"
          step={3}
          title="About your farm"
          lead="Five quick questions. Satellites filled in what they could; change anything that is wrong."
        >
          {d.setup.demo && (
            <p className={styles.demoNote}>
              Starting from demo answers. Change anything that doesn’t match your farm.
            </p>
          )}

          <Question n={1} id="q-field" title={m.questions.field.title} why={m.questions.field.why}>
            <p className={styles.confirm}>
              <span className={styles.tick} aria-hidden="true">
                ✓
              </span>
              <span>
                Satellites are watching <strong>{d.watch_label}</strong>
                {d.area_ha !== null && <>, about {Math.round(d.area_ha)} ha</>}.{" "}
                <Link href="/#analyze">Use a different field</Link>
              </span>
            </p>
          </Question>

          <Question n={2} id="q-crops" title={m.questions.crops.title} why={m.questions.crops.why}>
            <CropSlots
              scope="field"
              crops={answers.crops}
              choices={cashChoices}
              onCount={setCount}
              onPick={pickCrop}
            >
              <div className={styles.cover}>
                <label>
                  <span className="field-label">Cover crop in the bare months</span>
                  <select
                    className="select"
                    value={answers.cover ?? ""}
                    onChange={(e) => set({ cover: e.target.value || null })}
                  >
                    <option value="">No cover crop</option>
                    {(o?.cover_choices ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="caption">
                  Optional. Pick one only if you sow something while the field would be bare.
                </p>
              </div>
              {o && o.slots.length === answers.crops.length && (
                <div className={styles.monthsBox}>
                  <Disclosure summary="Adjust planting or harvest months">
                    <p className={`caption ${styles.monthsLead}`}>
                      Satellites suggest these months. Change them only if they are wrong.
                    </p>
                    <div className={styles.monthsGrid}>
                      {o.slots.map((s, i) => (
                        <div key={`${s.id}-${i}`} className={styles.monthsRow}>
                          <span className={styles.monthsCrop}>
                            {i + 1}. {s.name}
                          </span>
                          {(["plant", "harvest"] as const).map((k) => (
                            <label key={k}>
                              <span className="field-label">
                                {k === "plant" ? "Plant" : "Harvest"}
                              </span>
                              <select
                                className="select"
                                value={s[k]}
                                onChange={(e) => pickMonth(i, k, Number(e.target.value))}
                              >
                                {MONTHS.map((mo, mi) => (
                                  <option key={mo} value={mi + 1}>
                                    {mo}
                                  </option>
                                ))}
                              </select>
                            </label>
                          ))}
                        </div>
                      ))}
                    </div>
                  </Disclosure>
                </div>
              )}
              {o && (
                <div className={styles.farmYear}>
                  <h4>Your farming year</h4>
                  <YearStrip rows={o.farm_year} legend />
                </div>
              )}
            </CropSlots>
          </Question>

          <Question n={3} id="q-water" title={m.questions.water.title} why={m.questions.water.why}>
            <WaterTiles
              scope="field"
              choices={m.water}
              value={answers.water}
              help={m.water_help}
              onChange={(water) => set({ water })}
            />
          </Question>

          <Question n={4} id="q-soil" title={m.questions.soil.title} why={m.questions.soil.why}>
            <SoilTiles
              scope="field"
              choices={m.soil}
              value={answers.soil}
              help={m.soil_help}
              onChange={(soil) => set({ soil })}
            />
          </Question>

          <Question n={5} id="q-goals" title={m.questions.goals.title} why={m.questions.goals.why}>
            <GoalRanker
              goals={m.goals}
              order={answers.goals}
              onChange={(goals) => set({ goals })}
              emptyNote={m.no_goals_note}
            />
          </Question>
        </Section>

        <Section
          id="weather"
          step={4}
          title="What if the weather changes?"
          lead="Optional, and not a forecast: see which options still hold up if rain or heat shifted."
        >
          <div className={styles.weather}>
            <div>
              <p className={styles.sub}>If yearly rain changed</p>
              <TileGroup
                name="field-rain"
                legend="If yearly rain changed"
                tiles={RAIN_OPTIONS}
                value={answers.rain}
                onChange={(rain) => set({ rain })}
              />
            </div>
            <WarmingTiles scope="field" value={answers.temp} onChange={(temp) => set({ temp })} />
          </div>
        </Section>

        <Section
          id="options"
          step={5}
          title="Your options"
          lead="Your rotation next to the recommended and alternative options. Change any answer above and they update."
        >
          <OptionsPanel
            recommendation={o?.recommendation ?? null}
            note={o?.note ?? null}
            compare={o?.compare ?? []}
            others={o?.others}
            unsuitable={o?.unsuitable}
            pending={options.pending}
            error={options.error}
          />
        </Section>

        <Section
          id="reliability"
          step={6}
          title="How reliable is this?"
          lead="Where the numbers come from, and where human judgement still matters."
        >
          <div className={styles.reliability}>
            <div className="prose">
              {d.reliability.cross_check && <p>{d.reliability.cross_check}</p>}
              <p>
                Options are compared with each other using rules and published crop data. They are
                not yield or profit forecasts. Check machinery, seed, buyers and pest carryover with
                a local adviser before changing a rotation.
              </p>
            </div>
            <Disclosure summary={`Datasets and how recent they are (${d.reliability.coverage.length})`}>
              <dl className={styles.coverage}>
                {d.reliability.coverage.map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            </Disclosure>
          </div>
        </Section>
      </div>
    </article>
  );
}

function ReportSkeleton() {
  return (
    <div className={`page ${styles.skeleton}`} aria-busy="true" aria-label="Loading field report">
      <div className={styles.skLine} style={{ width: 110 }} />
      <div className={styles.skTitle} />
      <div className={styles.skLine} style={{ width: 320 }} />
      <div className={styles.skBlock} />
    </div>
  );
}
