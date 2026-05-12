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
  total: number;
  has_more: boolean;
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
  /** Majority matched_person_id across the cluster's detections — what
   *  the UI shows in the section header instead of repeating the name
   *  on every row. null when no detection in the cluster matched any
   *  enrolled person. */
  dominant_person_id?: string | null;
  dominant_person_name?: string | null;
  /** Fraction of detections that matched the dominant person (0..1).
   *  Used to flag mixed-attribution clusters where the matcher
   *  disagrees with itself within one visual identity. */
  dominant_share?: number | null;
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

// Voices tab — pyannote voice clusters aggregated per source. Pyannote
// already produces a per-source clustering (SPEAKER_NN labels on every
// turn), so this surface is pure aggregation over source_speakers — no
// HDBSCAN pass needed. Mirrors the FacePosition shape so the Voices
// panel can share the cluster-header / per-row layout.
export interface VoiceClusterTurn {
  segment_id: string;
  start_ts: number;
  end_ts: number;
  duration: number;
  /** Current attribution. null if the turn isn't attributed to a
   *  Person yet. */
  speaker_person_id: string | null;
  /** How this attribution was made — drives the row colour-coding so
   *  the operator can see at a glance which turns were 'voice+face'
   *  confirmed vs face-only vs manually assigned vs unresolved. */
  match_method: MatchMethod;
  /** False for sub-300ms turns whose embedding is NULL — these can't
   *  contribute to voiceprint enrolment but are still shown for review. */
  has_embedding: boolean;
  /** Full concatenated text of every chunk in this turn, soft-truncated
   *  to ~300 chars with an ellipsis. Empty when the turn has no
   *  source_chunks rows yet (transcription gap). */
  preview_text: string;
}

export interface VoiceCluster {
  /** pyannote label — e.g. "SPEAKER_00". Never null in this surface. */
  speaker_label: string;
  turn_count: number;
  total_seconds: number;
  /** Earliest start_ts across the cluster's turns. */
  first_ts: number;
  /** Latest end_ts across the cluster's turns. */
  last_ts: number;
  /** How many of this cluster's turns have a non-NULL embedding and so
   *  could contribute a voiceprint at bulk-assign time. Sub-300ms turns
   *  have NULL embeddings (see speaker-identification.md § Quality gates)
   *  and are excluded from the eligible count. */
  embedding_eligible_count: number;
  /** Majority speaker_person_id across the cluster's turns. null when
   *  no turn is attributed yet. */
  dominant_person_id: string | null;
  dominant_person_name: string | null;
  /** Fraction of turns that share dominant_person_id (0..1). */
  dominant_share: number | null;
  /** Per-match-method tally over the cluster's turns. "null" key is the
   *  count of unattributed turns. */
  match_method_breakdown: Record<string, number>;
  /** Every turn in the cluster, sorted chronologically by start_ts. */
  turns: VoiceClusterTurn[];
}

export interface VoiceClustersResponse {
  source_id: string;
  speakers: VoiceCluster[];
}

// Identity alignment tab — cross-modal matrix between face clusters
// (visual identity, from source_face_clusters / HDBSCAN over ArcFace
// embeddings) and voice clusters (audio identity, pyannote SPEAKER_NN
// labels). Read-only diagnostic; actions stay on the per-modality tabs.
export interface AlignmentFaceCluster {
  cluster_id: number;
  detection_count: number;
  dominant_person_id: string | null;
  dominant_person_name: string | null;
  dominant_share: number | null;
}

export interface AlignmentVoiceCluster {
  speaker_label: string;
  turn_count: number;
  total_seconds: number;
  dominant_person_id: string | null;
  dominant_person_name: string | null;
  dominant_share: number | null;
}

export interface AlignmentRow {
  face_cluster_id: number;
  speaker_label: string;
  /** Face detections whose frame_ts falls inside any turn for this
   *  speaker_label. At 1 fps detection-count ≈ seconds. */
  overlap_count: number;
  /** Subset of overlap_count where mouth-opening passed the ASD
   *  threshold — i.e. the face was probably speaking, not just visible. */
  active_overlap_count: number;
  face_cluster_share: number;
  voice_cluster_share: number;
  /** min(face_cluster_share, voice_cluster_share) — the limiting
   *  modality's share. */
  confidence: number;
}

export interface AlignmentDominantPair {
  face_cluster_id: number;
  speaker_label: string;
  confidence: number;
  overlap_count: number;
}

export interface AlignmentDisagreement {
  segment_id: string;
  start_ts: number;
  end_ts: number;
  speaker_label: string | null;
  speaker_person_id: string;
  speaker_person_name: string | null;
  face_cluster_id: number;
  face_person_id: string;
  face_person_name: string | null;
  active_overlap_count: number;
}

/** Per-turn alignment row in chronological order. Each row carries both
 *  modalities' cluster dominants, per-turn face counts, per-modality
 *  matches, the current attribution, and an agreement classification —
 *  the follow-along view of the identity-review surface. */
export type AlignmentAgreement = "agree" | "disagree" | "partial" | "none";

export interface AlignmentTimelineRow {
  segment_id: string;
  start_ts: number;
  end_ts: number;
  duration: number;

  speaker_label: string;
  voice_cluster_person_id: string | null;
  voice_cluster_person_name: string | null;

  face_cluster_id: number | null;
  face_cluster_person_id: string | null;
  face_cluster_person_name: string | null;
  total_face_count: number;
  /** Face frames inside this turn that passed the mouth-opening ASD
   *  threshold — "the visible face was probably speaking at that moment". */
  active_face_count: number;

  audio_match_person_id: string | null;
  audio_match_person_name: string | null;
  visual_match_person_id: string | null;
  visual_match_person_name: string | null;

  speaker_person_id: string | null;
  speaker_person_name: string | null;
  match_method: MatchMethod;
  match_confidence: number | null;

  agreement: AlignmentAgreement;
  preview_text: string;
}

/** Phase 1 face-driven transcript: chunks grouped into consecutive runs
 *  of the same dominant on-screen face cluster. ``pyannote_turn_ids`` lists
 *  the pyannote turn ids the run overlaps in time — combined with
 *  ``conflated_turn_ids`` it shows which pyannote turns merged across a
 *  face transition. */
export interface FaceTranscriptRun {
  face_cluster_id: number | null;
  face_cluster_person_id: string | null;
  face_cluster_person_name: string | null;
  start_ts: number;
  end_ts: number;
  duration: number;
  chunk_count: number;
  text: string;
  pyannote_turn_ids: string[];
}

export interface IdentityAlignmentResponse {
  source_id: string;
  face_clusters: AlignmentFaceCluster[];
  voice_clusters: AlignmentVoiceCluster[];
  alignment: AlignmentRow[];
  dominant_pairings: AlignmentDominantPair[];
  disagreements: AlignmentDisagreement[];
  timeline: AlignmentTimelineRow[];
  /** Chunks grouped by dominant on-screen face cluster — the
   *  "transcript as determined by face". */
  face_transcript: FaceTranscriptRun[];
  /** pyannote turn ids that contain chunks attributed to more than
   *  one face cluster — pyannote merged across a face transition. */
  conflated_turn_ids: string[];
}
