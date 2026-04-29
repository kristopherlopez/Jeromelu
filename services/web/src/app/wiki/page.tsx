import { apiFetch } from "@/lib/api";
import WikiIndexClient from "./WikiIndexClient";
import type { WikiPagesResponse } from "./wiki-data";

export const metadata = {
  title: "The Wiki | Jaromelu",
  description:
    "Browse everything Jaromelu knows — players, teams, voices, rounds.",
};

export default async function WikiPage({
  searchParams,
}: {
  searchParams: Promise<{ type?: string }>;
}) {
  const { type } = await searchParams;
  let pages: WikiPagesResponse["items"] = [];

  try {
    const pagesData = await apiFetch<WikiPagesResponse>(
      "/api/wiki/pages?limit=500",
    );
    pages = pagesData.items;
  } catch {
    // API may not be running
  }

  return <WikiIndexClient pages={pages} initialType={type} />;
}
