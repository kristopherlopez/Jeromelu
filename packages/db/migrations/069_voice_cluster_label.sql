-- Voice clustering layer above pyannote's per-source clustering.
--
-- Pyannote's ``speaker_label`` (SPEAKER_00, SPEAKER_01, …) is the raw
-- output of pyannote's segmentation + clustering pass. We treat it as
-- one *input* signal but not the source of truth — empirically pyannote
-- often conflates two co-commentators into a single SPEAKER_NN cluster,
-- especially with similar pitch / pacing. To support custom clustering
-- methods (HDBSCAN over wespeaker medoids, face-driven re-segmentation,
-- and manual edits) without losing pyannote's original assignment, add
-- a separate ``cluster_label`` column.
--
-- The Voices tab and AssignVoice flow read by ``coalesce(cluster_label,
-- speaker_label)``: if any clusterer has written here, use it; otherwise
-- fall back to pyannote. Re-running the diariser only repopulates
-- speaker_label and leaves cluster_label intact; re-running our HDBSCAN
-- pass overwrites cluster_label without touching speaker_label.

ALTER TABLE source_speakers
    ADD COLUMN cluster_label TEXT;

COMMENT ON COLUMN source_speakers.cluster_label IS
    'Output of post-pyannote clustering (HDBSCAN over per-turn wespeaker '
    'medoids, face-driven re-segmentation, or manual edits). NULL means '
    'no override — Voices tab falls back to speaker_label.';

-- Group-by performance: the Voices tab and Alignment endpoints aggregate
-- by document_id × coalesce(cluster_label, speaker_label). A plain index
-- on cluster_label is enough — speaker_label already has implicit lookup
-- coverage via existing document indexes.
CREATE INDEX idx_source_speakers_cluster_label
    ON source_speakers (document_id, cluster_label)
    WHERE cluster_label IS NOT NULL;
