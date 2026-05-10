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

  // Escape closes the modal — standard expectation; not having it reads
  // as "buggy" even if everything else works.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  const handleSave = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
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
        const text = await resp.text();
        throw new Error(`API ${resp.status}: ${text}`);
      }
      onSaved();
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

        {selected && (
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
