import { apiFetch } from "@/lib/api";
import WikiPageClient from "../../../components/WikiPageClient";
import type { WikiPageResponse } from "../../../wiki-data";

interface Props {
  params: Promise<{ season: string; round: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { season, round } = await params;
  const slug = `round-${season}-${round}`;
  try {
    const data = await apiFetch<WikiPageResponse>(
      `/api/wiki/pages/${slug}`
    );
    return {
      title: `${data.page.title} | Wiki | Jaromelu`,
      description: data.page.summary || `Round ${round}, ${season}`,
    };
  } catch {
    return { title: `Round ${round} ${season} | Wiki | Jaromelu` };
  }
}

export default async function RoundWikiPage({ params }: Props) {
  const { season, round } = await params;
  const slug = `round-${season}-${round}`;
  const data = await apiFetch<WikiPageResponse>(
    `/api/wiki/pages/${slug}`
  );

  return (
    <WikiPageClient
      page={data.page}
      revisions={data.revisions}
      linkedPages={data.linked_pages}
    />
  );
}
