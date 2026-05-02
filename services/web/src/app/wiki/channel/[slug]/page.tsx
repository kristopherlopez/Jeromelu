import { apiFetch } from "@/lib/api";
import ChannelView from "./ChannelView";
import type { ChannelEpisodesResponse } from "./episodes";
import type { WikiPageResponse, WikiPagesResponse } from "../../wiki-data";

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
    return { title: "Channel | Wiki | Jaromelu" };
  }
}

export default async function ChannelWikiPage({ params }: Props) {
  const { slug } = await params;
  const [data, related, episodes] = await Promise.all([
    apiFetch<WikiPageResponse>(`/api/wiki/pages/${slug}`),
    apiFetch<WikiPagesResponse>(`/api/wiki/pages?page_type=channel&limit=12`)
      .catch(() => ({ items: [], next_before: null }) as WikiPagesResponse),
    apiFetch<ChannelEpisodesResponse>(`/api/wiki/channels/${slug}/episodes?limit=6`)
      .catch(() => ({ items: [] }) as ChannelEpisodesResponse),
  ]);

  return (
    <ChannelView
      page={data.page}
      revisions={data.revisions}
      relatedChannels={related.items}
      episodes={episodes.items}
    />
  );
}
