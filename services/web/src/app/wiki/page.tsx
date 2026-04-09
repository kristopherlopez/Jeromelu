import { apiFetch } from "@/lib/api";
import WikiIndexClient from "./WikiIndexClient";
import type { WikiPagesResponse, WikiChangesResponse } from "./wiki-data";

export const metadata = {
  title: "The Wiki | Jaromelu",
  description:
    "Browse everything Jaromelu knows — players, teams, advisors, rounds.",
};

export default async function WikiPage() {
  let pages: WikiPagesResponse["items"] = [];
  let recentChanges: WikiChangesResponse["items"] = [];

  try {
    const [pagesData, changesData] = await Promise.all([
      apiFetch<WikiPagesResponse>("/api/wiki/pages?limit=500"),
      apiFetch<WikiChangesResponse>("/api/wiki/recent-changes?limit=10"),
    ]);
    pages = pagesData.items;
    recentChanges = changesData.items;
  } catch {
    // API may not be running
  }

  return <WikiIndexClient pages={pages} recentChanges={recentChanges} />;
}
