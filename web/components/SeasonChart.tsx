"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { MonthPoint } from "@/lib/types";
import { FULL_MONTHS as FULL, MONTHS } from "./YearStrip";
import styles from "./SeasonChart.module.css";

/** Longest unbroken run of months on the Jan–Dec axis, as [first, length]. */
function longestRun(months: number[]): [number, number] | null {
  const set = new Set(months);
  let best: [number, number] | null = null;
  for (let m = 1; m <= 12; m++) {
    if (!set.has(m) || set.has(m - 1)) continue;
    let len = 1;
    while (set.has(m + len)) len++;
    if (!best || len > best[1]) best = [m, len];
  }
  return best;
}

function niceStep(span: number) {
  const raw = span / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const n = raw / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(720);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/**
 * Plant greenness (line, 0–1), rain (bars, mm) and water balance (dashed, mm).
 * ``linked`` marks the month the timelapse is showing; ``onHover`` reports the
 * month under the pointer so the timelapse can follow.
 */
export function SeasonChart({
  months,
  bare,
  stress,
  linked = null,
  onHover,
}: {
  months: MonthPoint[];
  bare: number[];
  stress: number[];
  linked?: number | null;
  onHover?: (month: number | null) => void;
}) {
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  useEffect(() => {
    onHover?.(active);
  }, [active, onHover]);

  const compact = width < 560;
  const height = compact ? 260 : 320;
  const m = { l: compact ? 34 : 44, r: compact ? 40 : 52, t: 14, b: 30 };
  const w = Math.max(200, width - m.l - m.r);
  const h = height - m.t - m.b;
  const band = w / 12;
  const x = (month: number) => m.l + (month - 0.5) * band;

  const mmValues = months.flatMap((p) => [p.rain_mm ?? 0, p.water_balance_mm ?? 0]);
  const rawMin = Math.min(0, ...mmValues);
  const rawMax = Math.max(10, ...mmValues);
  const step = niceStep(rawMax - rawMin);
  const mmMin = Math.floor(rawMin / step) * step;
  const mmMax = Math.ceil(rawMax / step) * step;
  const yMm = (v: number) => m.t + h - ((v - mmMin) / (mmMax - mmMin)) * h;
  const yNdvi = (v: number) => m.t + h - v * h;
  const mmTicks: number[] = [];
  for (let v = mmMin; v <= mmMax + 1e-9; v += step) mmTicks.push(Math.round(v));

  const ndviPts = months.filter((p) => p.ndvi !== null);
  const ndviPath = ndviPts
    .map((p, i) => `${i ? "L" : "M"}${x(p.month).toFixed(1)},${yNdvi(p.ndvi!).toFixed(1)}`)
    .join(" ");
  const wbPts = months.filter((p) => p.water_balance_mm !== null);
  const wbPath = wbPts
    .map((p, i) => `${i ? "L" : "M"}${x(p.month).toFixed(1)},${yMm(p.water_balance_mm!).toFixed(1)}`)
    .join(" ");

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left - m.l;
    const month = Math.min(12, Math.max(1, Math.floor(mx / band) + 1));
    setActive(month);
  };
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "ArrowRight") setActive((a) => Math.min(12, (a ?? 0) + 1));
    else if (e.key === "ArrowLeft") setActive((a) => Math.max(1, (a ?? 2) - 1));
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
  };

  const point = active ? months.find((p) => p.month === active) : undefined;
  const tipLeft = active ? Math.min(Math.max(x(active), 90), width - 90) : 0;

  // Direct labels instead of legend entries: on the bands, and at the greenest month.
  const bandLabel = (run: [number, number] | null, long: string, short: string) => {
    if (!run) return null;
    const room = run[1] * band - 12;
    const text = room >= long.length * 6.4 ? long : room >= short.length * 6.4 ? short : null;
    return text && { x: m.l + (run[0] - 1) * band + 6, text };
  };
  const bareLabel = bandLabel(longestRun(bare), "Usually bare", "Bare");
  const stressLabel = bandLabel(longestRun(stress), "Growing-season stress", "Stress");
  const peak = ndviPts.reduce<MonthPoint | null>(
    (b, p) => (b === null || p.ndvi! > b.ndvi! ? p : b),
    null,
  );

  return (
    <figure className={styles.figure}>
      <ul className={styles.legend} aria-hidden="true">
        <li>
          <i className={styles.keyLine} />
          Plant greenness (0–1)
        </li>
        <li>
          <i className={styles.keyBar} />
          Rain (mm)
        </li>
        <li>
          <i className={styles.keyDash} />
          Water balance (mm)
        </li>
      </ul>

      <div ref={wrapRef} className={styles.wrap}>
        <svg
          width={width}
          height={height}
          className={styles.svg}
          role="img"
          aria-label="Seasonal chart of plant greenness, rain and water balance. Use the arrow keys to read each month."
          tabIndex={0}
          onPointerMove={onMove}
          onPointerLeave={() => setActive(null)}
          onKeyDown={onKey}
          onBlur={() => setActive(null)}
        >
          {bare.map((mo) => (
            <rect
              key={`b${mo}`}
              x={m.l + (mo - 1) * band}
              y={m.t}
              width={band}
              height={h}
              className={styles.bareBand}
            />
          ))}
          {stress.map((mo) => (
            <rect
              key={`s${mo}`}
              x={m.l + (mo - 1) * band}
              y={m.t}
              width={band}
              height={h}
              className={styles.stressBand}
            />
          ))}
          {linked && (
            <rect
              x={m.l + (linked - 1) * band}
              y={m.t}
              width={band}
              height={h}
              rx={4}
              className={styles.linked}
            />
          )}
          {bareLabel && (
            <text x={bareLabel.x} y={m.t + 14} className={styles.bareLabel}>
              {bareLabel.text}
            </text>
          )}
          {stressLabel && (
            <text x={stressLabel.x} y={m.t + 14} className={styles.stressLabel}>
              {stressLabel.text}
            </text>
          )}

          {[0, 0.25, 0.5, 0.75, 1].map((v) => (
            <g key={v}>
              <line x1={m.l} x2={m.l + w} y1={yNdvi(v)} y2={yNdvi(v)} className={styles.grid} />
              <text x={m.l - 8} y={yNdvi(v)} className={styles.tickL} dominantBaseline="middle">
                {v.toFixed(v === 0 || v === 1 ? 0 : 2).replace(/^0\./, ".")}
              </text>
            </g>
          ))}
          {mmTicks.map((v) => (
            <text key={v} x={m.l + w + 8} y={yMm(v)} className={styles.tickR} dominantBaseline="middle">
              {v}
            </text>
          ))}
          {mmMin < 0 && (
            <line x1={m.l} x2={m.l + w} y1={yMm(0)} y2={yMm(0)} className={styles.zero} />
          )}

          {months.map((p) =>
            p.rain_mm ? (
              <rect
                key={`r${p.month}`}
                x={x(p.month) - band * 0.28}
                width={band * 0.56}
                y={yMm(Math.max(0, p.rain_mm))}
                height={Math.abs(yMm(0) - yMm(p.rain_mm))}
                rx={3}
                className={styles.bar}
              />
            ) : null,
          )}
          <path d={wbPath} className={styles.balance} />
          <path d={ndviPath} className={styles.ndvi} />
          {ndviPts.map((p) => (
            <circle
              key={`n${p.month}`}
              cx={x(p.month)}
              cy={yNdvi(p.ndvi!)}
              r={active === p.month ? 5.5 : 3.5}
              className={styles.dotN}
            />
          ))}

          {peak && (
            <text
              x={Math.min(Math.max(x(peak.month), m.l + 48), m.l + w - 48)}
              y={yNdvi(peak.ndvi!) - 12 < m.t + 30 ? yNdvi(peak.ndvi!) + 22 : yNdvi(peak.ndvi!) - 12}
              textAnchor="middle"
              className={styles.peakLabel}
            >
              Peak greenness
            </text>
          )}

          {MONTHS.map((mo, i) => (
            <text
              key={mo}
              x={x(i + 1)}
              y={height - 8}
              className={`${styles.tickX} ${linked === i + 1 ? styles.tickOn : ""}`}
              textAnchor="middle"
            >
              {compact ? mo[0] : mo}
            </text>
          ))}

          {active && (
            <line x1={x(active)} x2={x(active)} y1={m.t} y2={m.t + h} className={styles.guide} />
          )}
        </svg>

        {point && active && (
          <div className={styles.tip} style={{ left: tipLeft }} aria-live="polite">
            <p className={styles.tipMonth}>{FULL[active - 1]}</p>
            <dl>
              <div>
                <dt>
                  <i className={styles.keyLine} />
                  Greenness
                </dt>
                <dd>{point.ndvi !== null ? point.ndvi.toFixed(2) : "—"}</dd>
              </div>
              <div>
                <dt>
                  <i className={styles.keyBar} />
                  Rain
                </dt>
                <dd>{point.rain_mm !== null ? `${point.rain_mm.toFixed(0)} mm` : "—"}</dd>
              </div>
              <div>
                <dt>
                  <i className={styles.keyDash} />
                  Water balance
                </dt>
                <dd>
                  {point.water_balance_mm !== null ? `${point.water_balance_mm.toFixed(0)} mm` : "—"}
                </dd>
              </div>
            </dl>
            {(bare.includes(active) || stress.includes(active)) && (
              <p className={styles.tipNote}>
                {bare.includes(active) ? "Usually bare" : "Growing-season stress"}
              </p>
            )}
          </div>
        )}
      </div>

      <table className="sr-only">
        <caption>Monthly values</caption>
        <thead>
          <tr>
            <th>Month</th>
            <th>Plant greenness</th>
            <th>Rain (mm)</th>
            <th>Water balance (mm)</th>
          </tr>
        </thead>
        <tbody>
          {months.map((p) => (
            <tr key={p.month}>
              <td>{FULL[p.month - 1]}</td>
              <td>{p.ndvi?.toFixed(2) ?? "—"}</td>
              <td>{p.rain_mm?.toFixed(0) ?? "—"}</td>
              <td>{p.water_balance_mm?.toFixed(0) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
