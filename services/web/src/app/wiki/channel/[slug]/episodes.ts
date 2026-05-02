export interface ChannelEpisode {
  source_id: string;
  title: string;
  description: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  canonical_url: string | null;
  published_at: string | null;
  is_short: boolean;
  ingestion_status: string;
}

export interface ChannelEpisodesResponse {
  items: ChannelEpisode[];
}
