"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { API_BASE } from "@/lib/api";
import type { PersonSummary, Speaker } from "@/lib/types";
import PersonPicker from "./PersonPicker";

interface Props {
  sourceId: string;
  speaker: Speaker;
  frameTs: number;
  bbox: [number, number, number, number] | null;
  onClose: () => void;
  onSaved: () => void;
}

// The picker can return either an existing Person row or a free-text
// name the operator wants to create. Discriminated union so the save
// handler can shape the request body correctly.
type Selection =
  | { kind: "existing"; person: PersonSummary }
  | { kind: "new"; name: string };

// One row in the live checklist. The backend emits
// {step, status, detail?} events as work progresses; this maps each to
// the UI state machine.
type StepStatus = "pending" | "running" | "done" | "skip" | "error";
type StepKey = "person" | "frame" | "face" | "voice" | "commit";

interface StepEvent {
  step: StepKey | "result" | "unknown";
  status: "start" | "done" | "skip" | "error";
  // The detail payload varies per step; we only consume a few fields,
  // so unknown is fine here.
  detail?: unknown;
}

const STEPS: { key: StepKey; label: string }[] = [
  { key: "person", label: "Resolved person" },
  { key: "frame", label: "Pulled video frame" },
  { key: "face", label: "Enrolled face" },
  { key: "voice", label: "Enrolled voice" },
  { key: "commit", label: "Saved to database" },
];

function stepIcon(s: StepStatus): string {
  switch (s) {
    case "pending":
      return "○";
    case "running":
      return "⟳";
    case "done":
      return "✓";
    case "skip":
      return "⊘";
    case "error":
      return "✗";
  }
}

function stepColor(s: StepStatus): string {
  switch (s) {
    case "pending":
      return "var(--foreground-ghost)";
    case "running":
      return "var(--accent)";
    case "done":
      return "var(--accent)";
    case "skip":
      return "var(--foreground-secondary)";
    case "error":
      return "#f87171"; // red-400
  }
}

export default function ReassignFaceModal({
  sourceId,
  speaker,
  frameTs,
  bbox,
  onClose,
  onSaved,
}: Props) {
  const [selected, setSelected] = useState<Selection | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<Record<StepKey, StepStatus>>({
    person: "pending",
    frame: "pending",
    face: "pending",
    voice: "pending",
    commit: "pending",
  });

  // Escape closes the modal — standard expectation; not having it reads
  // as "buggy" even if everything else works.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  const applyEvent = (evt: StepEvent) => {
    if (evt.step === "result" && evt.status === "done") {
      // Stream's terminal success — let the caller close + refresh.
      onSaved();
      return;
    }
    if (evt.step === "unknown" || (evt.status === "error" && evt.step !== "result")) {
      const detail = typeof evt.detail === "string" ? evt.detail : "stream error";
      setError(detail);
      setSteps((prev) => {
        // Mark whatever was running as errored so the UI doesn't sit
        // on a frozen ⟳ icon.
        const next = { ...prev };
        if (evt.step !== "unknown" && evt.step in next) {
          next[evt.step as StepKey] = "error";
        }
        return next;
      });
      return;
    }
    if (evt.step === "result") return;
    const key = evt.step as StepKey;
    setSteps((prev) => {
      const next = { ...prev };
      if (evt.status === "start") next[key] = "running";
      else if (evt.status === "done") next[key] = "done";
      else if (evt.status === "skip") next[key] = "skip";
      else if (evt.status === "error") next[key] = "error";
      return next;
    });
  };

  const handleSave = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    setSteps({
      person: "pending",
      frame: "pending",
      face: "pending",
      voice: "pending",
      commit: "pending",
    });
    try {
      // Backend resolves target Person from exactly one of these:
      // existing person_id, or new_person_name (lookup-or-create).
      const personFields =
        selected.kind === "existing"
          ? { person_id: selected.person.person_id }
          : { new_person_name: selected.name };
      const resp = await fetch(
        `${API_BASE}/api/sources/${sourceId}/speakers/${speaker.segment_id}/reassign`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...personFields,
            frame_ts: frameTs,
            bbox,
          }),
        },
      );
      if (!resp.ok) {
        // 4xx validation errors come back as a normal JSON body, not
        // the stream — surface those before trying to read events.
        const text = await resp.text();
        throw new Error(`API ${resp.status}: ${text}`);
      }
      if (!resp.body) {
        throw new Error("Streaming not supported by this browser");
      }

      // NDJSON reader. The backend emits one JSON object per line; we
      // buffer across chunks because a chunk boundary can land mid-line.
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
            applyEvent(JSON.parse(line) as StepEvent);
          } catch {
            // Garbled line — log and keep going. Better to soldier on
            // and let later events update the UI than to bail entirely.
            console.error("reassign: failed to parse stream line", line);
          }
        }
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  // Portal to document.body — escapes any parent transform / overflow /
  // stacking-context that was clipping the modal to the VideoOverlay's
  // aspect-ratio box and letting clicks pass through to the transcript.
  if (typeof document === "undefined") return null;

  const overlay = (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.85)" }}
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-md flex-col gap-3 rounded-lg border p-5 shadow-xl"
        style={{
          borderColor: "var(--border)",
          // var(--surface) is one shade lighter than the page background
          // — reads as "raised card", not "blended into the page".
          backgroundColor: "var(--surface)",
          color: "var(--foreground)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold uppercase tracking-wider">
          Reassign speaker turn
        </h2>
        <div
          className="rounded border px-3 py-2 text-xs"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--background-deep)" }}
        >
          <div>
            <span style={{ color: "var(--foreground-ghost)" }}>Currently: </span>
            <strong>{speaker.speaker_person_name ?? speaker.speaker_label ?? "?"}</strong>
            {speaker.match_method && (
              <span className="ml-2" style={{ color: "var(--foreground-ghost)" }}>
                ({speaker.match_method},{" "}
                {speaker.match_confidence != null
                  ? `${(speaker.match_confidence * 100).toFixed(0)}%`
                  : "—"}
                )
              </span>
            )}
          </div>
          <div style={{ color: "var(--foreground-ghost)" }}>
            Turn: {speaker.start_ts.toFixed(1)}s – {speaker.end_ts.toFixed(1)}s · Frame: {frameTs.toFixed(1)}s
          </div>
        </div>

        <PersonPicker
          onSelect={(p) => setSelected({ kind: "existing", person: p })}
          onCreateNew={(name) => setSelected({ kind: "new", name })}
          autoFocus
        />

        {/* Pre-submit explainer — replaced by the live checklist while
            submitting so the user sees actual progress instead of a
            spinner sitting on a 30s+ S3 download. */}
        {!submitting && selected && (
          <div
            className="rounded border px-3 py-2 text-xs"
            style={{
              borderColor: "var(--accent)",
              color: "var(--foreground)",
            }}
          >
            {selected.kind === "existing" ? (
              <>
                Saving will assign this turn to{" "}
                <strong>{selected.person.canonical_name}</strong>, write a face
                embedding from the current frame, and a voiceprint from the
                turn audio.
              </>
            ) : (
              <>
                Saving will create a new Person <strong>{selected.name}</strong>{" "}
                (or reuse an existing one with the same canonical name), assign
                this turn to them, and write a face embedding + voiceprint from
                this turn.
              </>
            )}
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
            {STEPS.map(({ key, label }) => {
              const status = steps[key];
              return (
                <li
                  key={key}
                  className="flex items-center gap-2"
                  style={{ color: stepColor(status) }}
                >
                  <span
                    className="inline-block w-4 text-center"
                    style={{
                      // Spin the running glyph so it reads as active.
                      animation:
                        status === "running" ? "spin 1s linear infinite" : undefined,
                    }}
                  >
                    {stepIcon(status)}
                  </span>
                  <span>{label}</span>
                  {status === "skip" && (
                    <span style={{ color: "var(--foreground-ghost)" }}>
                      (skipped)
                    </span>
                  )}
                </li>
              );
            })}
            <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
          </ul>
        )}

        {error && (
          <p className="text-xs text-red-400">{error}</p>
        )}

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
            {submitting ? "Saving…" : "Save reassignment"}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body);
}
