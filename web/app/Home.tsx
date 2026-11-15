"use client";

import Link from "next/link";
import { useMemo } from "react";
import { AnalyzeField } from "@/components/AnalyzeField";
import { MapView } from "@/components/map/MapView";
import { YearStrip } from "@/components/YearStrip";
import { BROADBALK } from "@/lib/geo";
import { useGet, useLivePost } from "@/lib/hooks";
import type { Status, UkContext, UkOptions } from "@/lib/types";
import styles from "./Home.module.css";

export function Home() {
  const status = useGet<Status>("/api/status");
  const ctx = useGet<UkContext>("/api/uk/context");
  const body = useMemo(
    () =>
      ctx.data && {
        crops: ctx.data.default_rotation.slice(0, 3),
        goal_order: ctx.data.default_goal_order,
      },
    [ctx.data],
  );
  const uk = useLivePost<UkOptions>("/api/uk/options", body);
  const current = uk.data?.plans[0];

  return (
    <>
      <section className={`page ${styles.hero}`} aria-labelledby="hero-title">
        <div className={styles.heroHead}>
          <h1 id="hero-title" className={styles.headline}>
            See what NASA satellites know about your field.
          </h1>
          <div className={styles.heroAside}>
            <p className={styles.lede}>
              Then compare crop rotations that build soil and resilience — side by side, in plain
              words, with no scores to decode.
            </p>
            <div className={styles.ctas}>
              <Link className="btn btn-primary" href="/uk">
                Open the Broadbalk demo
              </Link>
              <a className="btn" href="#analyze">
                Analyze my own field
              </a>
            </div>
          </div>
        </div>

        <figure className={styles.visual}>
          <div className={styles.imagery}>
            <MapView
              center={[BROADBALK.lat, BROADBALK.lon]}
              zoom={16}
              height="100%"
              interactive={false}
              attributionPosition="topright"
              nudge={[0, 70]}
              marker={{ ...BROADBALK, label: "Broadbalk" }}
              label="Satellite image of the Broadbalk field at Rothamsted"
            />
            <p className={styles.chip}>
              <span className={styles.chipDot} aria-hidden="true" />
              Rothamsted, Harpenden · winter wheat since 1843
            </p>
          </div>
          <div className={styles.sheet}>
            <div className={styles.sheetHead}>
              <p className={styles.sheetTitle}>Broadbalk’s farming year</p>
              <p className={styles.sheetMeta}>
                {current ? current.steps.join(" → ") : "Loading the UK model…"}
              </p>
            </div>
            <div className={styles.strip}>
              {current ? (
                <YearStrip rows={current.calendar} size="hero" legend animate />
              ) : (
                <div className={styles.stripPlaceholder} aria-hidden="true" />
              )}
            </div>
          </div>
          <figcaption className={styles.caption}>
            Every option in Field Shift is laid out month by month like this, so you can see when
            the soil is covered and when it lies bare.
          </figcaption>
        </figure>
      </section>

      <section id="demo" className={`page ${styles.demo}`} aria-labelledby="demo-title">
        <div className={styles.demoCopy}>
          <h2 id="demo-title" className={styles.h2}>
            Try the demo field
          </h2>
          <p className={styles.body}>
            Rothamsted Broadbalk is the world’s longest-running field experiment, and the one
            field here with physical ground measurements: a rain gauge has recorded on this farm
            since 1853. The UK rotation model checks NASA satellite rainfall against that gauge.
          </p>
          <Link className="btn btn-primary" href="/uk">
            Open the UK model
          </Link>
        </div>
        <dl className={styles.demoFacts}>
          <div>
            <dt>Where</dt>
            <dd>Harpenden, United Kingdom</dd>
          </div>
          <div>
            <dt>Coordinates</dt>
            <dd className="num">51.809° N, 0.373° W</dd>
          </div>
          <div>
            <dt>Climate</dt>
            <dd>Temperate oceanic</dd>
          </div>
          <div>
            <dt>On record</dt>
            <dd>Winter wheat since 1843, rain gauge since 1853</dd>
          </div>
        </dl>
      </section>

      <section id="analyze" className={`page ${styles.analyze}`} aria-labelledby="analyze-title">
        <h2 id="analyze-title" className={styles.h2}>
          Analyze my own field
        </h2>
        <p className={`${styles.body} ${styles.analyzeLead}`}>
          Draw your field on the map or enter its coordinates. We outline it, read ten years of
          satellite and weather data for it, and open your field report.
        </p>
        <ol className={styles.steps}>
          <li>
            <strong>Find the field.</strong> Draw it, or enter latitude and longitude.
          </li>
          <li>
            <strong>Describe your farm.</strong> Crops, water, soil and what matters to you.
          </li>
          <li>
            <strong>Compare options.</strong> Your rotation next to better-fitting ones.
          </li>
        </ol>
        <AnalyzeField live={status.data?.live ?? false} statusKnown={!!status.data} />
      </section>
    </>
  );
}
