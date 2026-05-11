export interface SourceListItem {
  source_id: string;
  title: string;
  canonical_url: string | null;
  published_at: string | null;
  creator_name: string | null;
  claim_count: number;
  /** Channel that produced this source. Null for legacy rows without
   * a `channel_id`. Drives the voice chip on the wiki Sources card. */
  voice: {
    slug: string;
    name: string;
    logo_url: string | null;
  } | null;
}

export interface SourceListResponse {
  items: SourceListItem[];
}

export interface ChunkDetail {
  chunk_id: string;
  start_ts: number | null;
  end_ts: number | null;
  raw_text: string;
  clean_text: string | null;
}

export interface ClaimDetail {
  claim_id: string;
  claim_type: string;
  claim_text: string | null;
  polarity: number | null;
  strength: number | null;
  effective_round: number | null;
  season: number | null;
  start_ts: number | null;
  end_ts: number | null;
  player_name: string | null;
  chunks: ChunkDetail[];
}

export interface TranscriptChunk {
  chunk_id: string;
  chunk_index: number;
  raw_text: string;
  clean_text: string | null;
  start_ts: number | null;
  end_ts: number | null;
  has_claims: boolean;
  speaker_segment_id: string | null;
  paragraph_break: boolean;
}

export type MatchMethod = "voice" | "face" | "voice+face" | "manual" | null;

export interface Speaker {
  segment_id: string;
  speaker_label: string | null;
  speaker_person_id: string | null;
  speaker_person_name: string | null;
  start_ts: number;
  end_ts: number;
  // Phase 4 provenance — see source_speakers (mig 050).
  match_method: MatchMethod;
  match_confidence: number | null;
  audio_match_person_id: string | null;
  audio_match_person_name: string | null;
  audio_match_score: number | null;
  visual_match_person_id: string | null;
  visual_match_person_name: string | null;
  visual_match_score: number | null;
}

export interface SourceDetailResponse {
  source: {
    source_id: string;
    title: string;
    canonical_url: string | null;
    published_at: string | null;
    creator_name: string | null;
    source_type: string;
    // Phase 4 visual identification: presigned S3 URLs (1h TTL).
    // When both are present the review UI swaps the YouTube embed for
    // the local video + face overlay.
    video_url: string | null;
    face_track_url: string | null;
    video_format: "multi_cam" | "single_cam" | "audio_only" | null;
    ingestion_status: string;
    transcription_status: string | null;
  };
  claims: ClaimDetail[];
  chunks: TranscriptChunk[];
  speakers: Speaker[];
}

export interface PersonSummary {
  person_id: string;
  canonical_name: string;
  slug: string | null;
  aliases: string[];
}

// Phase 4 face-track JSON (persisted to S3 by visual_id.py). Fetched
// directly from `face_track_url` by the VideoOverlay.
export interface FaceTrackFace {
  bbox: [number, number, number, number];  // [x1, y1, x2, y2] in source pixel coords
  det_score: number;
  person_id: string | null;
  similarity: number | null;
  mouth_opening: number | null;
}

export interface FaceTrackFrame {
  ts: number;
  faces: FaceTrackFace[];
}

export interface FaceTrack {
  json_version: number;
  embedding_model: string;
  embedding_dim: number;
  sample_rate: number;
  video_s3_key: string;
  video_format: "multi_cam" | "single_cam" | "audio_only";
  duration_seconds: number;
  // Source video pixel dims — bbox coords live in this space. Added in
  // json_version 4 so the overlay can scale to whatever surface it's
  // drawing over (HTML5 video uses videoWidth/Height, YouTube iframe
  // uses these instead). Optional for older v3 JSONs.
  frame_width?: number;
  frame_height?: number;
  frames: FaceTrackFrame[];
}

// Faces gallery (Slice A of the cluster-manager work). Aggregates the
// face-track JSON into per-Person groups for the gallery view at
// /wiki/source/[id]/faces. Fetched from /api/sources/{id}/face-groups.
export interface FaceGroupSample {
  ts: number;
  bbox: [number, number, number, number];
  det_score: number;
  similarity: number | null;
}

export interface FaceGroup {
  /** null = unassigned bucket. */
  person_id: string | null;
  person_name: string | null;
  detection_count: number;
  avg_det_score: number;
  avg_similarity: number | null;
  samples: FaceGroupSample[];
}

export interface FaceGroupsResponse {
  source_id: string;
  duration_seconds: number | null;
  frame_width: number | null;
  frame_height: number | null;
  total_faces: number;
  groups: FaceGroup[];
}

// Faces tab — per-position runs over the face-track JSON. Each run is
// one row in the UI: a stretch of frames at the same on-screen position
// where the matched person_id stays constant (with a small gap and
// flicker tolerance — see services/api/app/analyst/face_runs.py).
export interface FaceRunSample {
  ts: number;
  bbox: [number, number, number, number];
}

export interface FaceRunOverlapTurn {
  segment_id: string;
  start_ts: number;
  end_ts: number;
  speaker_label: string | null;
  speaker_person_id: string | null;
  speaker_person_name: string | null;
  match_method: MatchMethod;
}

export interface FaceRun {
  /** null = unassigned. */
  person_id: string | null;
  person_name: string | null;
  start_ts: number;
  end_ts: number;
  frame_count: number;
  avg_similarity: number | null;
  start_sample: FaceRunSample;
  end_sample: FaceRunSample;
  overlapping_turns: FaceRunOverlapTurn[];
  /**
   * Slice B cluster identifier within the source. null when the
   * runs came from the spatial-fallback path (source has no
   * persisted detections yet) or this run is in the Outliers bucket.
   */
  cluster_id?: number | null;
}

export type FaceClusterKind = "person" | "portrait" | "noise" | null;

export interface FaceClusterStats {
  mouth_open_std: number | null;
  centroid_std: number | null;
  temporal_density: number | null;
}

export interface FacePosition {
  position_id: number;
  /**
   * "Cluster A" / "Cluster B" / "Outliers" (Slice B detection path),
   * or "Left" / "Centre" / "Right" / "Position N" (legacy spatial
   * path). The semantic is "what visually identifies this group" —
   * face cluster when we have embeddings, screen position otherwise.
   */
  label: string;
  centroid: [number, number];
  detection_count: number;
  runs: FaceRun[];
  /**
   * Set when this entry represents a face cluster (Slice B). null for
   * the spatial fallback and for the Outliers bucket.
   */
  cluster_id?: number | null;
  /** Operator override kind. null = unreviewed. */
  kind?: FaceClusterKind;
  /** Heuristic-assigned kind. Same value as kind unless operator overrode. */
  detected_kind?: FaceClusterKind;
  /** Hidden from default view when true. */
  excluded?: boolean;
  /** Operator-provided friendly label override, distinct from the generated label. */
  label_override?: string | null;
  notes?: string | null;
  stats?: FaceClusterStats | null;
}

export interface FaceRunsResponse {
  source_id: string;
  duration_seconds: number | null;
  frame_width: number | null;
  frame_height: number | null;
  positions: FacePosition[];
  /** Count of clusters filtered out as excluded (portraits/noise). */
  excluded_count?: number;
}
