import { apiFetch } from "@/lib/api";
import WikiIndexClient from "./WikiIndexClient";
import type { WikiPagesResponse } from "./wiki-data";

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

  const pagesResult = await Promise.allSettled([
    apiFetch<WikiPagesResponse>("/api/wiki/pages?limit=2000"),
  ]);

  const pages =
    pagesResult[0].status === "fulfilled" ? pagesResult[0].value.items : [];

  return <WikiIndexClient pages={pages} initialType={type} />;
}
