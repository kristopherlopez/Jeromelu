"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { API_BASE } from "@/lib/api";
import type { FaceRunOverlapTurn, PersonSummary } from "@/lib/types";
import PersonPicker from "./PersonPicker";

interface Props {
  sourceId: string;
  /** Cluster being assigned — null for the Outliers (HDBSCAN-noise) bucket,
   *  which uses segment_ids only and skips the cluster-face-exemplar copy. */
  clusterId: number | null;
  clusterLabel: string;
  /** Deduped union of overlapping_turns across all runs in the cluster. */
  segments: FaceRunOverlapTurn[];
  totalDetections: number;
  currentPersonName?: string | null;
  /** Earliest detection ts across the cluster, for header context. */
  firstTs: number;
  /** Latest detection ts across the cluster, for header context. */
  lastTs: number;
  onClose: () => void;
  onSaved: () => void;
}

type Selection =
  | { kind: "existing"; person: PersonSummary }
  | { kind: "new"; name: string };

type PhaseStatus = "pending" | "running" | "done" | "skip" | "error";

/** The streamed phases the SQL-only bulk-assign emits, plus the
 *  framing person/result events. Per-turn events are gone — the loop
 *  was replaced by a single SQL UPDATE.
 *
 *  ``regen_face_track`` runs after commit and rebuilds the cached
 *  face-track JSON so the YouTube overlay reflects the new attribution.
 *  Failure here means the DB is correct but the overlay is stale — the
 *  user must see the row turn red and retry via the regenerate endpoint. */
type Phase = "cluster_face" | "attribute" | "commit" | "regen_face_track";

interface StreamEvent {
  step: "person" | Phase | "result" | "unknown" | "turn";
  status: "start" | "done" | "skip" | "error";
  detail?: unknown;
}

// The textual label shown in the running checklist. Kept separate
// from the wire step name so the user-facing copy can change without
// breaking the protocol contract.
const PHASE_LABELS: Record<Phase, string> = {
  cluster_face: "Copy face exemplars from cluster",
  attribute: "Attribute speaker turns to person",
  commit: "Commit transaction",
  regen_face_track: "Refresh overlay face-track JSON",
};

function fmtTs(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

const ERROR_TRUNCATE_AT = 300;

function ErrorDisplay({ error }: { error: string }) {
  const [expanded, setExpanded] = useState(false);
  if (!error) return null;
  const long = error.length > ERROR_TRUNCATE_AT;
  const visible = expanded || !long ? error : error.slice(0, ERROR_TRUNCATE_AT) + "…";
  return (
    <div className="rounded border border-red-500/40 px-3 py-2 text-xs">
      <pre
        className="whitespace-pre-wrap break-words font-mono text-[11px] text-red-400"
        style={{ margin: 0 }}
      >
        {visible}
      </pre>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 text-[10px] uppercase tracking-wider"
          style={{ color: "var(--foreground-secondary)" }}
        >
          {expanded
            ? "Collapse"
            : `Show full (${error.length.toLocaleString()} chars)`}
        </button>
      )}
      <div className="mt-1 text-[10px]" style={{ color: "var(--foreground-ghost)" }}>
        Full error also logged to dev-tools console.
      </div>
    </div>
  );
}

export default function AssignRunModal({
  sourceId,
  clusterId,
  clusterLabel,
  segments,
  totalDetections,
  currentPersonName,
  firstTs,
  lastTs,
  onClose,
  onSaved,
}: Props) {
  const turns = segments;
  const [selected, setSelected] = useState<Selection | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Three-row phase checklist replaces the old per-turn list. cluster_face
  // is only emitted in cluster mode; the row stays "pending" if we're
  // in the legacy fallback path.
  const [phases, setPhases] = useState<Record<Phase, PhaseStatus>>({
    cluster_face: "pending",
    attribute: "pending",
    commit: "pending",
    regen_face_track: "pending",
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  const applyEvent = (evt: StreamEvent) => {
    if (evt.step === "result" && evt.status === "done") {
      onSaved();
      return;
    }
    if (evt.step === "unknown" || (evt.status === "error" && evt.step !== "result")) {
      const detail =
        evt.detail !== null && typeof evt.detail === "object" && evt.detail !== undefined
          ? JSON.stringify(evt.detail)
          : String(evt.detail ?? "stream error");
      // Always log the full detail so the dev tools console has it
      // regardless of how the UI truncates the visible error.
      console.error(
        "[assign-cluster] stream error:",
        { step: evt.step, status: evt.status, detail: evt.detail },
      );
      setError(detail);
      // Mark the phase that was running as errored, if any.
      if (
        evt.step === "cluster_face" ||
        evt.step === "attribute" ||
        evt.step === "commit" ||
        evt.step === "regen_face_track"
      ) {
        setPhases((prev) => ({ ...prev, [evt.step as Phase]: "error" }));
      }
      return;
    }

    if (
      evt.step === "cluster_face" ||
      evt.step === "attribute" ||
      evt.step === "commit" ||
      evt.step === "regen_face_track"
    ) {
      const phase = evt.step as Phase;
      setPhases((prev) => {
        let status: PhaseStatus = prev[phase];
        if (evt.status === "start") status = "running";
        else if (evt.status === "done") status = "done";
        else if (evt.status === "skip") status = "skip";
        return { ...prev, [phase]: status };
      });
    }
    // person + result + (legacy) turn events handled implicitly.
  };

  const handleSave = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    setPhases({
      cluster_face: "pending",
      attribute: "pending",
      commit: "pending",
      regen_face_track: "pending",
    });
    try {
      const personFields =
        selected.kind === "existing"
          ? { person_id: selected.person.person_id }
          : { new_person_name: selected.name };
      // When the cluster has an id (Slice B path), send it so the
      // backend reuses the cluster's persisted face embeddings as
      // exemplars instead of re-fetching frames per turn. Falls back
      // to the slower per-turn flow for the Outliers bucket where
      // clusterId is null.
      const clusterField =
        clusterId !== null && clusterId !== undefined
          ? { cluster_id: clusterId }
          : {};
      const resp = await fetch(
        `${API_BASE}/api/sources/${sourceId}/face-runs/assign`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...personFields,
            ...clusterField,
            segment_ids: turns.map((t) => t.segment_id),
          }),
        },
      );
      if (!resp.ok) {
        const text = await resp.text();
        console.error(
          "[assign-cluster] HTTP error:",
          { status: resp.status, body: text },
        );
        throw new Error(`API ${resp.status}: ${text}`);
      }
      if (!resp.body) throw new Error("Streaming not supported in this browser");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let nl: number;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (!line) continue;
          try {
            applyEvent(JSON.parse(line) as StreamEvent);
          } catch {
            console.error("assign-run: bad line", line);
          }
        }
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (typeof document === "undefined") return null;

  const statusIcon = (s: PhaseStatus): string =>
    s === "pending"
      ? "○"
      : s === "running"
        ? "⟳"
        : s === "done"
          ? "✓"
          : s === "skip"
            ? "—"
            : "✗";
  const statusColor = (s: PhaseStatus): string =>
    s === "pending"
      ? "var(--foreground-ghost)"
      : s === "running"
        ? "var(--accent)"
        : s === "done"
          ? "var(--accent)"
          : s === "skip"
            ? "var(--foreground-ghost)"
            : "#f87171";

  const overlay = (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.85)" }}
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-lg flex-col gap-3 rounded-lg border p-5 shadow-xl"
        style={{
          borderColor: "var(--border)",
          backgroundColor: "var(--surface)",
          color: "var(--foreground)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold uppercase tracking-wider">
          Assign run
        </h2>
        <div
          className="rounded border px-3 py-2 text-xs"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--background-deep)" }}
        >
          <div>
            <strong>{clusterLabel}</strong>
            {" · "}
            <span style={{ color: "var(--foreground-ghost)" }}>
              Currently: {currentPersonName ?? "?"}
            </span>
          </div>
          <div style={{ color: "var(--foreground-ghost)" }}>
            {totalDetections.toLocaleString()} detections ·{" "}
            {fmtTs(firstTs)}–{fmtTs(lastTs)} ·{" "}
            {turns.length} overlapping turn{turns.length === 1 ? "" : "s"}
          </div>
        </div>

        <PersonPicker
          onSelect={(p) => setSelected({ kind: "existing", person: p })}
          onCreateNew={(name) => setSelected({ kind: "new", name })}
          autoFocus
        />

        {!submitting && selected && (
          <div
            className="rounded border px-3 py-2 text-xs"
            style={{ borderColor: "var(--accent)" }}
          >
            Saving will attribute all <strong>{turns.length}</strong> overlapping
            speaker turn{turns.length === 1 ? "" : "s"} to{" "}
            <strong>
              {selected.kind === "existing"
                ? selected.person.canonical_name
                : selected.name}
            </strong>
            {clusterId !== null && clusterId !== undefined && (
              <>
                {" "}and copy up to 10 face exemplars from the cluster's
                highest-confidence detections into their face registry.
              </>
            )}
            {" "}Single transaction — partial failures roll back the whole
            batch. Voice enrollment is intentionally skipped at bulk-assign
            time; a future workflow will sample representative turns for the
            voiceprint registry separately.
          </div>
        )}

        {submitting && (
          <ul
            className="flex flex-col gap-1 rounded border px-3 py-2 text-xs"
            style={{
              borderColor: "var(--border)",
              backgroundColor: "var(--background-deep)",
            }}
          >
            {(
              [
                {
                  key: "cluster_face" as Phase,
                  label: `${PHASE_LABELS.cluster_face} (${turns.length} turns to attribute)`,
                },
                {
                  key: "attribute" as Phase,
                  label: `Attribute ${turns.length} turn${turns.length === 1 ? "" : "s"} to person`,
                },
                {
                  key: "commit" as Phase,
                  label: PHASE_LABELS.commit,
                },
                {
                  key: "regen_face_track" as Phase,
                  label: PHASE_LABELS.regen_face_track,
                },
              ] as const
            ).map(({ key, label }) => (
              <li
                key={key}
                className="flex items-center gap-2"
                style={{ color: statusColor(phases[key]) }}
              >
                <span
                  className="inline-block w-4 text-center"
                  style={{
                    animation:
                      phases[key] === "running"
                        ? "spin 1s linear infinite"
                        : undefined,
                  }}
                >
                  {statusIcon(phases[key])}
                </span>
                <span>{label}</span>
              </li>
            ))}
            <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
          </ul>
        )}

        {error && <ErrorDisplay error={error} />}

        <div className="mt-2 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border px-3 py-1.5 text-xs"
            style={{ borderColor: "var(--border)", color: "var(--foreground-secondary)" }}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="rounded px-3 py-1.5 text-xs font-medium"
            style={{
              backgroundColor: selected ? "var(--accent)" : "var(--background-deep)",
              color: selected ? "#000" : "var(--foreground-ghost)",
              cursor: selected && !submitting ? "pointer" : "not-allowed",
            }}
            disabled={!selected || submitting}
          >
            {submitting ? "Assigning…" : "Assign run"}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body);
}
