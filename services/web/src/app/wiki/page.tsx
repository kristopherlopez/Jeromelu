import { apiFetch } from "@/lib/api";
import WikiIndexClient from "./WikiIndexClient";
import type { WikiPagesResponse } from "./wiki-data";
import type { SourceListResponse } from "@/lib/types";

export const metadata = {
  title: "The Wiki | Jaromelu",
  description:
    "Browse everything Jaromelu knows — players, teams, voices, sources.",
};

export default async function WikiPage({
  searchParams,
}: {
  searchParams: Promise<{ type?: string }>;
}) {
  const { type } = await searchParams;

  const [pagesResult, sourcesResult] = await Promise.allSettled([
    apiFetch<WikiPagesResponse>("/api/wiki/pages?limit=2000"),
    apiFetch<SourceListResponse>("/api/sources"),
  ]);

  const pages =
    pagesResult.status === "fulfilled" ? pagesResult.value.items : [];
  const sourceCount =
    sourcesResult.status === "fulfilled" ? sourcesResult.value.items.length : 0;

  return (
    <WikiIndexClient
      pages={pages}
      sourceCount={sourceCount}
      initialType={type}
    />
  );
}
