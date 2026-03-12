export interface SourceListItem {
  source_id: string;
  title: string;
  canonical_url: string | null;
  published_at: string | null;
  creator_name: string | null;
  claim_count: number;
}

export interface SourceListResponse {
  items: SourceListItem[];
}

export interface ChunkDetail {
  chunk_id: string;
  start_ts: number | null;
  end_ts: number | null;
  text: string;
}

export interface ClaimDetail {
  claim_id: string;
  claim_type: string;
  claim_text: string | null;
  polarity: number | null;
  strength: number | null;
  effective_round: number | null;
  season: number | null;
  player_name: string | null;
  chunks: ChunkDetail[];
}

export interface TranscriptChunk {
  chunk_id: string;
  chunk_index: number;
  text: string;
  start_ts: number | null;
  end_ts: number | null;
  has_claims: boolean;
}

export interface SourceDetailResponse {
  source: {
    source_id: string;
    title: string;
    canonical_url: string | null;
    published_at: string | null;
    creator_name: string | null;
    source_type: string;
  };
  claims: ClaimDetail[];
  chunks: TranscriptChunk[];
}
