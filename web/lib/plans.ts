import type { CalendarRow, Plan } from "./types";

/** Months a year the soil carries a crop or a cover crop, averaged over the rotation. */
export function coveredMonths(rows: CalendarRow[]): number | null {
  if (!rows.length) return null;
  const bare = rows.reduce(
    (n, r) => n + r.segments.filter((s) => !s.crop_id).reduce((m, s) => m + s.span, 0),
    0,
  );
  return Math.round(12 - bare / rows.length);
}

/** The plan the live panel shows: the recommended one, else the farmer's own. */
export function livePlan(plans: Plan[]) {
  const best = plans.find((p) => p.role === "recommended") ?? null;
  const current = plans.find((p) => p.role === "current") ?? null;
  return { best, current, shown: best ?? current };
}
