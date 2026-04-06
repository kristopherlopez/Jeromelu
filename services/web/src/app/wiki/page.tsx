import { apiFetch } from "@/lib/api";
import WikiIndexClient from "./WikiIndexClient";
import type { WikiPagesResponse } from "./wiki-data";

export const metadata = {
  title: "The Wiki | Jeromelu",
  description:
    "Browse everything Jeromelu knows — players, teams, advisors, rounds.",
};

export default async function WikiPage() {
  let pages: WikiPagesResponse["items"] = [];

  try {
    const data = await apiFetch<WikiPagesResponse>("/api/wiki/pages?limit=500");
    pages = data.items;
  } catch {
    // API may not be running
  }

  return <WikiIndexClient pages={pages} />;
}
