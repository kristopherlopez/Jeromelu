import { apiFetch } from "@/lib/api";
import WikiPageClient from "../../components/WikiPageClient";
import type { WikiPageResponse } from "../../wiki-data";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  try {
    const data = await apiFetch<WikiPageResponse>(
      `/api/wiki/pages/${slug}`
    );
    return {
      title: `${data.page.title} | Wiki | Jaromelu`,
      description: data.page.summary || `Wiki page for ${data.page.title}`,
    };
  } catch {
    return { title: "Player | Wiki | Jaromelu" };
  }
}

export default async function PlayerWikiPage({ params }: Props) {
  const { slug } = await params;
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
