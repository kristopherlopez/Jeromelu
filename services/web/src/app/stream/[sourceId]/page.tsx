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

  let data: SourceDetailResponse;
  try {
    data = await apiFetch<SourceDetailResponse>(`/api/sources/${sourceId}`);
  } catch {
    notFound();
  }

  let allSources: SourceListResponse = { items: [] };
  try {
    allSources = await apiFetch<SourceListResponse>("/api/sources");
  } catch {
    // Non-critical — related sources just won't show
  }

  return <SourceReviewClient data={data} allSources={allSources.items} />;
}
