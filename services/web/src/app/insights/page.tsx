import { apiFetch } from "@/lib/api";
import InsightsClient from "./InsightsClient";
import type { InsightListResponse } from "./insights-data";

export const metadata = {
  title: "The Analysis | Jaromelu",
  description:
    "Tips, picks, and consensus. Every round, every angle.",
};

export const dynamic = "force-dynamic";

export default async function InsightsPage() {
  let items: InsightListResponse["items"] = [];

  try {
    const data = await apiFetch<InsightListResponse>("/api/insights?limit=50");
    items = data.items;
  } catch {
    // API may not be running
  }

  return <InsightsClient items={items} />;
}
