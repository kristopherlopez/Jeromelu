import { notFound } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { SourceDetailResponse, SourceListResponse } from "@/lib/types";
import SourceReviewClient from "./SourceReviewClient";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ sourceId: string }>;
}

export default async function SourceDetailPage({ params }: Props) {
  const { sourceId } = await params;

  // The API returns a usable payload (with empty chunks/claims) for sources
  // that haven't been transcribed yet, so we only fall through to notFound()
  // for genuinely missing sources / network errors.
  let data: SourceDetailResponse;
  try {
    data = await apiFetch<SourceDetailResponse>(`/api/sources/${sourceId}`);
  } catch {
    notFound();
  }

  let allSources: SourceListResponse = { items: [], total: 0, has_more: false };
  try {
    // Related-sources panel only needs ~5 matches by same creator, so cap the
    // fetch — the full sources table is ~100k+ rows.
    allSources = await apiFetch<SourceListResponse>("/api/sources?limit=200");
  } catch {
    // Non-critical — related sources just won't show
  }

  return <SourceReviewClient data={data} allSources={allSources.items} />;
}
