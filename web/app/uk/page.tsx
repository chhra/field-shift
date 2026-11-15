import type { Metadata } from "next";
import { UkModel } from "./UkModel";

export const metadata: Metadata = { title: "UK rotation model" };

export default async function UkPage({
  searchParams,
}: {
  searchParams: Promise<{ lat?: string; lon?: string }>;
}) {
  const { lat, lon } = await searchParams;
  const la = lat !== undefined ? Number(lat) : NaN;
  const lo = lon !== undefined ? Number(lon) : NaN;
  const point = Number.isFinite(la) && Number.isFinite(lo) ? { lat: la, lon: lo } : null;
  return <UkModel point={point} />;
}
