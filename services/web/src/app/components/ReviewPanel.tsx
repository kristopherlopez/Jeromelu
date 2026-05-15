"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetch } from "@/lib/api";
import type {
  ReviewVoiceTimelineResponse,
  ReviewVoiceTurn,
  ReviewWord,
  ReviewWordAttributionResponse,
} from "@/lib/types";

interface Props {
  sourceId: string;
  /** Player's current time in seconds. Updated continuously by the
   *  YouTube embed via the parent component. */
  currentTime: number;
  /** Seek the player when the operator clicks a row. */
  onSeek: (seconds: number) => void;
}

function fmtTs(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function fmtDuration(seconds: number): string {
  if (seconds < 1) return `${seconds.toFixed(1)}s`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s ? ` ${s}s` : ""}`;
}

// Stable colour palette shared between cluster and person colouring.
// Same one used in FacesPanel / FaceTranscriptPanel so the same hue
// identifies the same identity across tabs.
const IDENTITY_PALETTE = [
  "#60a5fa", "#fbbf24", "#4ade80", "#c084fc",
  "#f87171", "#22d3ee", "#fb923c", "#a3e635",
  "#f472b6", "#94a3b8", "#facc15", "#34d399",
];

function colorForCluster(cid: number | null | undefined): string {
  if (cid === null || cid === undefined) return "var(--foreground-ghost)";
  return IDENTITY_PALETTE[cid % IDENTITY_PALETTE.length];
}

function colorForPerson(personId: string | null | undefined): string {
  if (!personId) return "var(--foreground-ghost)";
  // Deterministic hash: first 8 hex chars of the UUID → palette index.
  // Same person_id → same hue across every word/face/pill on the page
  // AND across two clusters that happen to be the same person.
  const hash = parseInt(personId.replace(/-/g, "").slice(0, 8), 16) || 0;
  return IDENTITY_PALETTE[hash % IDENTITY_PALETTE.length];
}

/** Person-first colouring. When an attribution exists (manual or kNN),
 *  colour by the person — so two clusters belonging to the same person
 *  (different camera angles, embedding drift) read as the same hue.
 *  Falls back to the cluster colour when unassigned, and to ghost grey
 *  when no cluster either. */
function colorForFace(
  cid: number | null | undefined,
  clusterPersonId: string | null | undefined,
  detectionPersonId: string | null | undefined,
): string {
  if (clusterPersonId) return colorForPerson(clusterPersonId);
  if (detectionPersonId) return colorForPerson(detectionPersonId);
  return colorForCluster(cid);
}

function methodColor(method: string | null): string {
  switch (method) {
    case "voice+face": return "#4ade80";
    case "voice":      return "#60a5fa";
    case "face":       return "#fbbf24";
    case "manual":     return "#c084fc";
    default:           return "var(--foreground-ghost)";
  }
}

export default function ReviewPanel({
  sourceId,
  currentTime,
  onSeek,
}: Props) {
  const [turns, setTurns] = useState<ReviewVoiceTurn[]>([]);
  const [words, setWords] = useState<ReviewWord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch in parallel — both are read-only, both are needed before
      // the panel can render meaningfully. The word-attribution call
      // is the heavier of the two (~11k rows for a 50-min source);
      // we still hold it in memory because lookups need to be O(log n).
      const [tl, wa] = await Promise.all([
        apiFetch<ReviewVoiceTimelineResponse>(
          `/api/sources/${sourceId}/voice-timeline`,
        ),
        apiFetch<ReviewWordAttributionResponse>(
          `/api/sources/${sourceId}/word-attribution`,
        ),
      ]);
      setTurns(tl.turns);
      setWords(wa.words);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [sourceId]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  // Binary search: find the active voice turn for the current playhead.
  const activeTurnIdx = useMemo(() => {
    if (turns.length === 0) return -1;
    // Find the turn whose [start_ts, end_ts) contains currentTime.
    // Linear scan would be fine at ~900 rows but binary is cleaner.
    let lo = 0;
    let hi = turns.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const t = turns[mid];
      if (currentTime < t.start_ts) {
        hi = mid - 1;
      } else if (currentTime >= t.end_ts) {
        lo = mid + 1;
      } else {
        return mid;
      }
    }
    return -1;
  }, [turns, currentTime]);

  const activeWordIdx = useMemo(() => {
    if (words.length === 0) return -1;
    // Words are sorted by start. Active = word whose [start, end)
    // contains currentTime; if between words, return the most-recent
    // word that started.
    let lo = 0;
    let hi = words.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const w = words[mid];
      if (currentTime < w.start) {
        hi = mid - 1;
      } else if (currentTime >= w.end) {
        lo = mid + 1;
      } else {
        return mid;
      }
    }
    return Math.max(0, hi);
  }, [words, currentTime]);

  const activeTurn = activeTurnIdx >= 0 ? turns[activeTurnIdx] : null;
  const activeWord = activeWordIdx >= 0 ? words[activeWordIdx] : null;

  // For each word, compute which voice turn (by index) contains its
  // start timestamp. -1 means no turn contains the word — typically
  // gaps between turns or words before/after the last turn.
  //
  // Two-pointer walk: both lists are sorted by time, so this is O(N+M).
  // Used by WordTranscript to render a turn-number superscript on the
  // first word that crosses into each new turn.
  const wordToTurnIdx = useMemo(() => {
    const out: number[] = new Array(words.length).fill(-1);
    if (turns.length === 0 || words.length === 0) return out;
    let ti = 0;
    for (let wi = 0; wi < words.length; wi++) {
      const ws = words[wi].start;
      while (ti < turns.length && turns[ti].end_ts <= ws) ti++;
      if (ti < turns.length && turns[ti].start_ts <= ws) {
        out[wi] = ti;
      }
    }
    return out;
  }, [words, turns]);

  // Set of word indices that are the first word in their voice turn.
  // These render a superscript turn number so the operator can see at
  // a glance where pyannote / HDBSCAN drew each turn boundary.
  const firstWordOfTurn = useMemo(() => {
    const out = new Set<number>();
    let prev = -2;
    for (let i = 0; i < wordToTurnIdx.length; i++) {
      const cur = wordToTurnIdx[i];
      if (cur !== prev && cur !== -1) out.add(i);
      prev = cur;
    }
    return out;
  }, [wordToTurnIdx]);

  // Auto-scroll both lists so the active row stays in view as playback
  // advances. Refs are keyed by index so we can find the right element
  // without searching the DOM. Smooth scroll feels janky during fast
  // playback so we use 'auto' for the actual scrollIntoView.
  const turnRefs = useRef<Map<number, HTMLLIElement>>(new Map());
  const wordRefs = useRef<Map<number, HTMLSpanElement>>(new Map());

  useEffect(() => {
    if (activeTurnIdx < 0) return;
    const el = turnRefs.current.get(activeTurnIdx);
    el?.scrollIntoView({ behavior: "auto", block: "center" });
  }, [activeTurnIdx]);

  useEffect(() => {
    if (activeWordIdx < 0) return;
    const el = wordRefs.current.get(activeWordIdx);
    el?.scrollIntoView({ behavior: "auto", block: "center" });
  }, [activeWordIdx]);

  if (loading && turns.length === 0) {
    return (
      <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        Loading review data…
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-xs" style={{ color: "#f87171" }}>
        Failed to load: {error}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-hidden">
      {/* 1. STATUS PILL — face + voice + word at playhead */}
      <PlayheadStatusPill
        currentTime={currentTime}
        activeTurn={activeTurn}
        activeWord={activeWord}
      />

      {/* 2 + 3. Two-column scroll: voice turn list on the left,
          word-level transcript on the right. Both auto-scroll to the
          active row as playback advances. */}
      <div className="grid flex-1 min-h-0 grid-cols-2 gap-3">
        <VoiceTurnList
          turns={turns}
          activeIdx={activeTurnIdx}
          onSeek={onSeek}
          turnRefs={turnRefs}
        />
        <WordTranscript
          words={words}
          activeIdx={activeWordIdx}
          onSeek={onSeek}
          wordRefs={wordRefs}
          wordToTurnIdx={wordToTurnIdx}
          firstWordOfTurn={firstWordOfTurn}
        />
      </div>
    </div>
  );
}

interface PlayheadStatusPillProps {
  currentTime: number;
  activeTurn: ReviewVoiceTurn | null;
  activeWord: ReviewWord | null;
}

function PlayheadStatusPill({
  currentTime,
  activeTurn,
  activeWord,
}: PlayheadStatusPillProps) {
  const visible = activeWord?.visible_faces ?? [];
  const hasActive = activeWord?.active_speaker != null;

  return (
    <section
      className="grid grid-cols-3 gap-2 rounded border px-3 py-2"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--background-deep)",
      }}
    >
      {/* FACE column — every detection at the playhead frame.
          Speaking faces marked with an ●; non-speaking faces still
          shown so the operator can tell "X is on screen but quiet"
          from "no face detected at this moment". */}
      <div className="flex flex-col gap-0.5">
        <h4
          className="text-[10px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--foreground-ghost)" }}
        >
          Faces at {fmtTs(currentTime)}
          {visible.length > 0 && (
            <span style={{ color: "var(--foreground-ghost)" }}>
              {" "}· {visible.length} on screen
              {hasActive ? "" : " · none speaking"}
            </span>
          )}
        </h4>
        {visible.length === 0 ? (
          <div className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
            no face detected
          </div>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {visible.map((f, idx) => {
              const name =
                f.cluster_attributed_person_name ??
                f.per_detection_matched_person_name ??
                null;
              const isCluster = f.cluster_attributed_person_name != null;
              return (
                <li
                  key={`${f.face_cluster_id ?? "none"}-${idx}`}
                  className="flex items-center gap-1.5 text-[11px]"
                  style={{
                    opacity: f.is_excluded ? 0.45 : f.is_active_speaker ? 1 : 0.7,
                    textDecoration: f.is_excluded ? "line-through" : "none",
                  }}
                >
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{
                      backgroundColor: colorForFace(
                        f.face_cluster_id,
                        f.cluster_attributed_person_id,
                        f.per_detection_matched_person_id,
                      ),
                    }}
                  />
                  <span className="font-semibold">
                    FACE_{f.face_cluster_id ?? "?"}
                  </span>
                  {name && (
                    <span
                      style={{
                        color: isCluster
                          ? "var(--accent)"
                          : "var(--foreground-secondary)",
                      }}
                    >
                      {isCluster ? "→" : "kNN→"} <strong>{name}</strong>
                    </span>
                  )}
                  {!name && (
                    <span style={{ color: "var(--foreground-ghost)" }}>
                      unassigned
                    </span>
                  )}
                  <span style={{ color: "var(--foreground-ghost)" }}>
                    · mouth {(f.mouth_opening * 100).toFixed(1)}%
                  </span>
                  {f.is_active_speaker && (
                    <span
                      className="rounded px-1 text-[9px] font-semibold uppercase"
                      style={{
                        backgroundColor: "var(--accent)",
                        color: "var(--background)",
                        textDecoration: "none",
                      }}
                      title="Mouth opening above ASD threshold — this face is speaking"
                    >
                      speaking
                    </span>
                  )}
                  {f.is_excluded && (
                    <span
                      className="rounded border px-1 text-[9px] font-semibold uppercase"
                      style={{
                        borderColor: "var(--foreground-ghost)",
                        color: "var(--foreground-ghost)",
                        textDecoration: "none",
                      }}
                      title="Cluster marked excluded (noise/portrait/duplicate) — ineligible to be the active speaker"
                    >
                      excluded
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* VOICE column — both labels shown side-by-side */}
      <div className="flex flex-col gap-0.5">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "var(--foreground-ghost)" }}>
          Voice at {fmtTs(currentTime)}
        </h4>
        {activeTurn ? (
          <>
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              {activeTurn.cluster_label && (
                <span
                  className="rounded border px-1 py-px font-semibold"
                  style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
                  title="HDBSCAN cluster label"
                >
                  {activeTurn.cluster_label}
                </span>
              )}
              {activeTurn.speaker_label && (
                <span
                  className="rounded border px-1 py-px"
                  style={{ borderColor: "var(--foreground-ghost)", color: "var(--foreground-secondary)" }}
                  title="Pyannote raw label"
                >
                  {activeTurn.speaker_label}
                </span>
              )}
              <span style={{ color: "var(--foreground-ghost)" }}>
                · {fmtDuration(activeTurn.duration)}
              </span>
            </div>
            <div className="text-[11px]">
              {activeTurn.person_name ? (
                <>
                  <span style={{ color: methodColor(activeTurn.match_method) }}>
                    ●
                  </span>
                  <span> </span>
                  <strong>{activeTurn.person_name}</strong>
                  <span style={{ color: "var(--foreground-ghost)" }}>
                    {" "}({activeTurn.match_method ?? "none"})
                  </span>
                </>
              ) : (
                <span style={{ color: "var(--foreground-ghost)" }}>
                  unattributed
                  {!activeTurn.has_embedding && " · no embedding"}
                </span>
              )}
            </div>
          </>
        ) : (
          <div className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
            no voice turn at playhead
          </div>
        )}
      </div>

      {/* WORD column */}
      <div className="flex flex-col gap-0.5">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "var(--foreground-ghost)" }}>
          Word at {fmtTs(currentTime)}
        </h4>
        {activeWord ? (
          <>
            <div className="text-xs font-semibold">{activeWord.word}</div>
            <div className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
              {fmtTs(activeWord.start)}–{fmtTs(activeWord.end)} · conf {(activeWord.confidence * 100).toFixed(0)}%
            </div>
          </>
        ) : (
          <div className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
            no word at playhead
          </div>
        )}
      </div>
    </section>
  );
}

interface VoiceTurnListProps {
  turns: ReviewVoiceTurn[];
  activeIdx: number;
  onSeek: (seconds: number) => void;
  turnRefs: React.MutableRefObject<Map<number, HTMLLIElement>>;
}

function VoiceTurnList({
  turns,
  activeIdx,
  onSeek,
  turnRefs,
}: VoiceTurnListProps) {
  return (
    <section
      className="flex min-h-0 flex-col rounded border"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--background-deep)" }}
    >
      <header
        className="border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider"
        style={{ borderColor: "var(--border)", color: "var(--foreground-secondary)" }}
      >
        Voice turns ({turns.length})
      </header>
      <ul className="flex-1 overflow-y-auto custom-scrollbar">
        {turns.map((t, idx) => {
          const isActive = idx === activeIdx;
          return (
            <li
              key={t.segment_id}
              ref={(el) => {
                if (el) turnRefs.current.set(idx, el);
                else turnRefs.current.delete(idx);
              }}
            >
              <button
                type="button"
                onClick={() => onSeek(t.start_ts)}
                className="flex w-full flex-col items-start gap-0.5 border-b px-3 py-1.5 text-left transition-colors"
                style={{
                  borderColor: "var(--border)",
                  backgroundColor: isActive ? "var(--accent-faint, rgba(96,165,250,0.15))" : "transparent",
                }}
              >
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span
                    className="font-mono font-semibold"
                    style={{ color: "var(--foreground-ghost)", minWidth: "2.5em" }}
                  >
                    #{idx + 1}
                  </span>
                  <span style={{ color: methodColor(t.match_method) }}>●</span>
                  {t.cluster_label && (
                    <span
                      className="rounded border px-1 font-semibold"
                      style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
                    >
                      {t.cluster_label}
                    </span>
                  )}
                  {t.speaker_label && (
                    <span
                      className="rounded border px-1"
                      style={{
                        borderColor: "var(--foreground-ghost)",
                        color: "var(--foreground-secondary)",
                      }}
                    >
                      {t.speaker_label}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span className="font-mono" style={{ color: "var(--foreground-ghost)" }}>
                    {fmtTs(t.start_ts)} – {fmtTs(t.end_ts)}
                  </span>
                  <span style={{ color: "var(--foreground-ghost)" }}>
                    · {fmtDuration(t.duration)}
                  </span>
                </div>
                <div className="text-[11px]">
                  {t.person_name ? (
                    <strong>{t.person_name}</strong>
                  ) : (
                    <span style={{ color: "var(--foreground-ghost)" }}>
                      unattributed{!t.has_embedding && " · no embedding"}
                    </span>
                  )}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

interface WordTranscriptProps {
  words: ReviewWord[];
  activeIdx: number;
  onSeek: (seconds: number) => void;
  wordRefs: React.MutableRefObject<Map<number, HTMLSpanElement>>;
  /** Word-index → voice-turn-index (or -1). Drives superscript display. */
  wordToTurnIdx: number[];
  /** Word indices that are the first word in their voice turn. Get a
   *  small superscript number so the operator can see at a glance where
   *  each voice turn starts. */
  firstWordOfTurn: Set<number>;
}

function WordTranscript({
  words,
  activeIdx,
  onSeek,
  wordRefs,
  wordToTurnIdx,
  firstWordOfTurn,
}: WordTranscriptProps) {
  return (
    <section
      className="flex min-h-0 flex-col rounded border"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--background-deep)" }}
    >
      <header
        className="border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider"
        style={{ borderColor: "var(--border)", color: "var(--foreground-secondary)" }}
      >
        Transcript ({words.length} words, coloured by active face)
      </header>
      <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-2 text-sm leading-snug">
        {words.map((w, idx) => {
          const isActive = idx === activeIdx;
          const cid = w.active_speaker?.face_cluster_id ?? null;
          // Person-first colouring: if the active speaker maps to a
          // person (via cluster attribution or per-detection kNN),
          // colour the word by the person — so two camera-angle
          // clusters that map to the same human read as one colour.
          // Falls back to the cluster colour when no attribution.
          const color = colorForFace(
            cid,
            w.active_speaker?.cluster_attributed_person_id ?? null,
            w.active_speaker?.per_detection_matched_person_id ?? null,
          );
          const personLabel =
            w.active_speaker?.cluster_attributed_person_name ??
            w.active_speaker?.per_detection_matched_person_name ??
            null;
          const turnNum = firstWordOfTurn.has(idx)
            ? wordToTurnIdx[idx] + 1
            : null;
          return (
            <span
              key={idx}
              ref={(el) => {
                if (el) wordRefs.current.set(idx, el);
                else wordRefs.current.delete(idx);
              }}
              onClick={() => onSeek(w.start)}
              className="cursor-pointer"
              style={{
                color,
                backgroundColor: isActive ? "var(--accent-faint, rgba(96,165,250,0.25))" : "transparent",
                padding: "0 1px",
                borderRadius: 2,
              }}
              title={
                w.active_speaker
                  ? `FACE_${cid}${personLabel ? ` → ${personLabel}` : ""} · ${fmtTs(w.start)}`
                  : `no active face · ${fmtTs(w.start)}`
              }
            >
              {turnNum !== null && (
                <sup
                  className="font-semibold"
                  style={{
                    color: "var(--accent)",
                    fontSize: "0.65em",
                    marginRight: 1,
                  }}
                  title={`Voice turn #${turnNum} starts here`}
                >
                  {turnNum}
                </sup>
              )}
              {w.word}{" "}
            </span>
          );
        })}
      </div>
    </section>
  );
}
