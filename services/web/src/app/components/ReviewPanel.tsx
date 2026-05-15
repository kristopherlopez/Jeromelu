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

// Stable per-cluster colour palette, same one used in FacesPanel /
// FaceTranscriptPanel so the same hue identifies the same cluster
// across tabs.
const CLUSTER_PALETTE = [
  "#60a5fa", "#fbbf24", "#4ade80", "#c084fc",
  "#f87171", "#22d3ee", "#fb923c", "#a3e635",
  "#f472b6", "#94a3b8", "#facc15", "#34d399",
];
function colorForCluster(cid: number | null | undefined): string {
  if (cid === null || cid === undefined) return "var(--foreground-ghost)";
  return CLUSTER_PALETTE[cid % CLUSTER_PALETTE.length];
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
  const faceCid = activeWord?.active_speaker?.face_cluster_id ?? null;
  // Face cluster's manual attribution wins over the per-detection kNN
  // match. The pill surfaces both so disagreement is visible.
  const faceClusterPerson = activeWord?.active_speaker?.cluster_attributed_person_name ?? null;
  const facePerDetPerson = activeWord?.active_speaker?.per_detection_matched_person_name ?? null;

  return (
    <section
      className="grid grid-cols-3 gap-2 rounded border px-3 py-2"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--background-deep)",
      }}
    >
      {/* FACE column */}
      <div className="flex flex-col gap-0.5">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "var(--foreground-ghost)" }}>
          Face at {fmtTs(currentTime)}
        </h4>
        {activeWord?.active_speaker ? (
          <>
            <div className="flex items-center gap-1.5 text-xs">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: colorForCluster(faceCid) }}
              />
              <span className="font-semibold">FACE_{faceCid}</span>
              <span style={{ color: "var(--foreground-ghost)" }}>
                · mouth {(activeWord.active_speaker.mouth_opening * 100).toFixed(1)}%
              </span>
            </div>
            <div className="text-[11px]">
              {faceClusterPerson ? (
                <span style={{ color: "var(--accent)" }}>
                  cluster → <strong>{faceClusterPerson}</strong>
                </span>
              ) : facePerDetPerson ? (
                <span style={{ color: "var(--foreground-secondary)" }}>
                  kNN → {facePerDetPerson}
                  <span style={{ color: "var(--foreground-ghost)" }}>
                    {" "}(cluster unassigned)
                  </span>
                </span>
              ) : (
                <span style={{ color: "var(--foreground-ghost)" }}>unassigned</span>
              )}
            </div>
          </>
        ) : (
          <div className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
            no face speaking
          </div>
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
                  <span style={{ color: "var(--foreground-ghost)" }}>
                    {fmtTs(t.start_ts)} · {fmtDuration(t.duration)}
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
}

function WordTranscript({
  words,
  activeIdx,
  onSeek,
  wordRefs,
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
          const color = colorForCluster(cid);
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
                  ? `FACE_${cid}${w.active_speaker.cluster_attributed_person_name ? ` → ${w.active_speaker.cluster_attributed_person_name}` : ""} · ${fmtTs(w.start)}`
                  : `no active face · ${fmtTs(w.start)}`
              }
            >
              {w.word}{" "}
            </span>
          );
        })}
      </div>
    </section>
  );
}
