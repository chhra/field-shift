import type { Metadata } from "next";
import { FieldReport } from "./FieldReport";

export const metadata: Metadata = { title: "Field report" };

export default async function FieldPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const { id } = await searchParams;
  return <FieldReport fieldId={id || "iowa"} />;
}
