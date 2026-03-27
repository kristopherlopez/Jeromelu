import { apiFetch } from "@/lib/api";
import FeedClient from "./FeedClient";
import type { FeedResponse } from "./feed-data";

export const metadata = {
  title: "The Feed | Jeromelu",
  description: "What I'm seeing, thinking, and doing. Ask me anything.",
};

export default async function FeedPage() {
  let items: FeedResponse["items"] = [];
  try {
    const data = await apiFetch<FeedResponse>("/api/feed?limit=50");
    items = data.items;
  } catch {
    // API may not be running — render empty feed
  }
  return <FeedClient items={items} />;
}
