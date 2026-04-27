export type WikiPageType = "player" | "team" | "advisor" | "round" | "channel";

export interface WikiPageSummary {
  page_id: string;
  slug: string;
  title: string;
  page_type: WikiPageType;
  summary: string | null;
  status: string;
  metadata_json: Record<string, unknown>;
  updated_at: string;
}

export interface WikiEntity {
  entity_id: string;
  canonical_name: string;
  entity_type: string;
  metadata_json: Record<string, unknown>;
}

export interface WikiChannel {
  channel_id: string;
  slug: string;
  platform: string;
  name: string;
  url: string | null;
  description: string | null;
  quality_rating: number;
  tags: string[];
  active: boolean;
  last_polled_at: string | null;
}

export interface WikiPageDetail {
  page_id: string;
  slug: string;
  title: string;
  page_type: WikiPageType;
  content: string;
  summary: string | null;
  status: string;
  metadata_json: Record<string, unknown>;
  entity: WikiEntity | null;
  channel: WikiChannel | null;
  updated_at: string;
  revision_count: number;
}

export interface WikiRevisionItem {
  revision_id: string;
  section_heading: string | null;
  summary: string;
  source_trigger: string | null;
  created_at: string;
}

export interface WikiChangeItem {
  revision_id: string;
  page_slug: string;
  page_title: string;
  page_type: WikiPageType;
  section_heading: string | null;
  summary: string;
  created_at: string;
}

export interface WikiLinkedPages {
  [slug: string]: { title: string; page_type: WikiPageType };
}

export interface WikiPagesResponse {
  items: WikiPageSummary[];
  next_before: string | null;
}

export interface WikiPageResponse {
  page: WikiPageDetail;
  revisions: WikiRevisionItem[];
  linked_pages: WikiLinkedPages;
}

export interface WikiChangesResponse {
  items: WikiChangeItem[];
  next_before: string | null;
}
