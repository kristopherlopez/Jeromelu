import { apiFetch } from "@/lib/api";
import ArticleClient from "./ArticleClient";
import type { InsightDetail } from "../insights-data";

export const dynamic = "force-dynamic";

export default async function InsightDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let article: InsightDetail | null = null;
  try {
    article = await apiFetch<InsightDetail>(`/api/insights/${id}`);
  } catch {
    // API may not be running or article not found
  }

  return <ArticleClient article={article} />;
}
