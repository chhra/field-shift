import type { GeoJSONPolygon } from "./types";

/** Rothamsted Broadbalk, the UK model's default field. */
export const BROADBALK = { lat: 51.809, lon: -0.373 };

/** Approximate area in hectares (equirectangular shoelace), as fieldshift.geo does. */
export function areaHa(points: [number, number][]): number {
  if (points.length < 3) return 0;
  const lat0 = (points.reduce((s, p) => s + p[0], 0) / points.length) * (Math.PI / 180);
  const mPerDegLat = 111_320;
  const mPerDegLon = 111_320 * Math.cos(lat0);
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    const [la1, lo1] = points[i];
    const [la2, lo2] = points[(i + 1) % points.length];
    sum += lo1 * mPerDegLon * (la2 * mPerDegLat) - lo2 * mPerDegLon * (la1 * mPerDegLat);
  }
  return Math.abs(sum) / 2 / 10_000;
}

/** Leaflet [lat, lon] corners → a closed GeoJSON polygon ([lon, lat]). */
export function toPolygon(points: [number, number][]): GeoJSONPolygon {
  const ring = points.map(([lat, lon]) => [lon, lat] as [number, number]);
  return { type: "Polygon", coordinates: [[...ring, ring[0]]] };
}
