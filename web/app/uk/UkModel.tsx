"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Disclosure } from "@/components/Disclosure";
import { FactGrid } from "@/components/FactGrid";
import {
  CropSlots,
  OptionsPanel,
  SoilTiles,
  WarmingTiles,
  WaterTiles,
} from "@/components/FarmInputs";
import { GoalRanker } from "@/components/GoalRanker";
import { MapView } from "@/components/map/MapView";
import { Banner, Question, Rich, Section } from "@/components/Report";
import { BROADBALK } from "@/lib/geo";
import { useGet, useLivePost } from "@/lib/hooks";
import type { GoalKey, InputsMeta, SoilKey, UkContext, UkOptions, UkRequest, WaterKey } from "@/lib/types";
import styles from "../field/FieldReport.module.css";
import uk from "./UkModel.module.css";

interface Answers {
  crops: string[];
  water: WaterKey;
  soil: SoilKey;
  goals: GoalKey[];
  warming: number;
}

export function UkModel({ point }: { point: { lat: number; lon: number } | null }) {
  const query = point ? `?lat=${point.lat}&lon=${point.lon}` : "";
  const ctx = useGet<UkContext>(`/api/uk/context${query}`);
  const meta = useGet<InputsMeta>("/api/meta/inputs");
  const [answers, setAnswers] = useState<Answers | null>(null);

  useEffect(() => {
    if (!ctx.data) return;
    setAnswers({
      crops: ctx.data.default_rotation.slice(0, 3),
      water: "rain_only",
      soil: "loamy",
      goals: ctx.data.default_goal_order,
      warming: 0,
    });
  }, [ctx.data]);

  const body: UkRequest | null = useMemo(
    () =>
      answers &&
      ctx.data && {
        crops: answers.crops,
        water: answers.water,
        soil: answers.soil,
        goal_order: answers.goals,
        warming_c: answers.warming,
        lat: ctx.data.at_location ? (point?.lat ?? null) : null,
        lon: ctx.data.at_location ? (point?.lon ?? null) : null,
      },
    [answers, ctx.data, point],
  );
  const options = useLivePost<UkOptions>("/api/uk/options", body);

  if (ctx.error) {
    return (
      <div className={`page ${styles.message}`}>
        <h1>The UK model isn’t available</h1>
        <p>{ctx.error}</p>
        <Link className="btn btn-primary" href="/">
          Back to Home
        </Link>
      </div>
    );
  }
  if (!ctx.data || !meta.data || !answers) {
    return (
      <div className={`page ${styles.skeleton}`} aria-busy="true" aria-label="Loading the UK model">
        <div className={styles.skTitle} />
        <div className={styles.skBlock} />
      </div>
    );
  }

  const c = ctx.data;
  const m = meta.data;
  const o = options.data;
  const set = (patch: Partial<Answers>) => setAnswers((a) => (a ? { ...a, ...patch } : a));
  const choices = c.crop_choices.map((name) => ({ id: name, name }));
  const where = c.at_location && point ? point : BROADBALK;

  const setCount = (n: number) => {
    const crops = answers.crops.slice(0, n);
    for (const name of [...c.default_rotation, ...c.crop_choices]) {
      if (crops.length >= n) break;
      if (!crops.includes(name)) crops.push(name);
    }
    set({ crops });
  };

  return (
    <article className={styles.report}>
      <header className={`page ${styles.head}`}>
        <p className={styles.kicker}>UK rotation model</p>
        <h1 className={styles.title}>{c.place}</h1>
        <p className={uk.intro}>
          Three crop rotations for one UK field: yours, a recommended option, and an alternative.
          Compare them side by side.
        </p>
        {c.location_error && <Banner tone="note">{c.location_error}</Banner>}
      </header>

      <div className="page">
        <Section id="the-field" step={1} title="The field" lead={c.field_text}>
          <div className={uk.fieldGrid}>
            <MapView
              center={[where.lat, where.lon]}
              zoom={c.at_location ? 13 : 15}
              height={340}
              marker={{ ...where, label: c.at_location ? "Your field" : "Broadbalk" }}
              label={`Satellite map of ${c.place}`}
            />
            <FactGrid facts={c.facts} />
          </div>
          {c.station && (
            <div className={uk.station}>
              <Disclosure summary="How the satellite data compares with the rain gauge on this farm">
                <div className="prose">
                  <p>
                    NASA POWER rainfall is a model and satellite estimate averaged over a grid cell
                    about 50 km wide. Rothamsted has measured rain with a gauge on this farm since
                    1853. Over {c.station.period} ({c.station.months_compared} months):
                  </p>
                  <dl className={uk.gauge}>
                    <div>
                      <dt>Average year</dt>
                      <dd>
                        NASA <strong className="num">{c.station.nasa_mm} mm</strong>, gauge{" "}
                        <strong className="num">{c.station.gauge_mm} mm</strong> (
                        {c.station.bias_pct > 0 ? "+" : ""}
                        {c.station.bias_pct}%)
                      </dd>
                    </div>
                    <div>
                      <dt>Month to month</dt>
                      <dd>
                        Correlation <strong className="num">{c.station.correlation}</strong>,
                        typical error{" "}
                        <strong className="num">{c.station.mean_abs_error_mm} mm</strong>
                      </dd>
                    </div>
                    <div>
                      <dt>Wettest months</dt>
                      <dd>
                        NASA <strong className="num">{c.station.wet_nasa_mm} mm</strong> against
                        the gauge’s <strong className="num">{c.station.wet_gauge_mm} mm</strong> (
                        {c.station.wet_pct > 0 ? "+" : ""}
                        {c.station.wet_pct}%)
                      </dd>
                    </div>
                  </dl>
                  <p>
                    Extremes are smoothed, so the wet-month erosion risk below is more likely
                    understated than overstated.
                  </p>
                  <p className="caption">{c.station.source}</p>
                </div>
              </Disclosure>
            </div>
          )}
        </Section>

        <Section
          id="farm"
          step={2}
          title="About your farm"
          lead="Four quick questions. Change anything that does not match your farm."
        >
          <Question n={1} id="uk-crops" title={m.questions.crops.title} why={m.questions.crops.why}>
            <p className={`caption ${uk.cropsNote}`}>
              One main crop per harvest year, in order. A ley counts once and stays three years.
              Leave cover crops out: the model adds them where the soil would be bare.
            </p>
            <CropSlots
              scope="uk"
              crops={answers.crops}
              choices={choices}
              onCount={setCount}
              onPick={(slot, id) =>
                set({ crops: answers.crops.map((x, i) => (i === slot ? id : x)) })
              }
            />
          </Question>

          <Question n={2} id="uk-water" title={m.questions.water.title} why={m.questions.water.why}>
            <WaterTiles
              scope="uk"
              choices={m.water}
              value={answers.water}
              help={m.water_help}
              onChange={(water) => set({ water })}
            />
          </Question>

          <Question n={3} id="uk-soil" title={m.questions.soil.title} why={m.questions.soil.why}>
            <SoilTiles
              scope="uk"
              choices={m.soil}
              value={answers.soil}
              help={m.soil_help}
              onChange={(soil) => set({ soil })}
            />
          </Question>

          <Question n={4} id="uk-goals" title={m.questions.goals.title} why={m.questions.goals.why}>
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
          step={3}
          title="What if the weather changes?"
          lead="Optional, and not a forecast: see which options still hold up if seasons ran warmer."
        >
          <WarmingTiles
            scope="uk"
            value={answers.warming}
            onChange={(warming) => set({ warming })}
          />
        </Section>

        <Section
          id="options"
          step={4}
          title="Your options"
          lead="Your rotation next to the recommended and alternative options. Change any answer above and they update."
        >
          <OptionsPanel
            recommendation={o?.recommendation ?? null}
            note={o?.note ?? null}
            compare={o?.plans ?? []}
            pending={options.pending}
            error={options.error}
          />
        </Section>

        <Section
          id="reliability"
          step={5}
          title="How reliable is this?"
          lead="This tool supports your judgement and your agronomist’s. It does not replace them."
        >
          <ul className={uk.caveats}>
            {c.reliability.map((line, i) => (
              <li key={i}>
                <Rich text={line} />
              </li>
            ))}
          </ul>
          <div className={uk.sources}>
            <Disclosure summary="Data sources">
              <dl className={styles.coverage}>
                {c.data_sources.map(([what, src]) => (
                  <div key={what}>
                    <dt>{what}</dt>
                    <dd className={uk.src}>{src}</dd>
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
