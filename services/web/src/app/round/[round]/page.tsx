import { notFound } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { RoundOverviewResponse } from "../round-data";
import RoundClient from "./RoundClient";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ round: string }>;
}

export default async function RoundPage({ params }: Props) {
  const { round } = await params;
  const roundNum = parseInt(round, 10);
  if (isNaN(roundNum) || roundNum < 1) notFound();

  let data: RoundOverviewResponse;
  try {
    data = await apiFetch<RoundOverviewResponse>(`/api/round/${roundNum}`);
  } catch {
    notFound();
  }

  return <RoundClient data={data} />;
}
