"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { API_BASE } from "@/lib/api";
import type { FaceRun, PersonSummary } from "@/lib/types";
import PersonPicker from "./PersonPicker";

interface Props {
  sourceId: string;
  run: FaceRun;
  onClose: () => void;
  onSaved: () => void;
}

type Selection =
  | { kind: "existing"; person: PersonSummary }
  | { kind: "new"; name: string };

type TurnStatus = "pending" | "running" | "done" | "error";

interface StreamEvent {
  step: "person" | "turn" | "commit" | "result" | "unknown";
  status: "start" | "done" | "skip" | "error";
  detail?: unknown;
}

function fmtTs(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export default function AssignRunModal({
  sourceId,
  run,
  onClose,
  onSaved,
}: Props) {
  const turns = run.overlapping_turns;
  const [selected, setSelected] = useState<Selection | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // One status per overlapping turn, indexed by position in the turns
  // array (matches the API's emitted index).
  const [turnStatus, setTurnStatus] = useState<TurnStatus[]>(() =>
    turns.map(() => "pending"),
  );
  const [commitStatus, setCommitStatus] =
    useState<TurnStatus>("pending");

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
      setError(detail);
      // Mark the turn that was running as errored, if any.
      setTurnStatus((prev) => {
        const next = [...prev];
        const idx =
          evt.detail !== null && typeof evt.detail === "object"
            ? (evt.detail as { index?: number }).index
            : undefined;
        if (typeof idx === "number" && idx >= 0 && idx < next.length) {
          next[idx] = "error";
        }
        return next;
      });
      if (evt.step === "commit") setCommitStatus("error");
      return;
    }

    if (evt.step === "turn") {
      const idx =
        evt.detail !== null && typeof evt.detail === "object"
          ? (evt.detail as { index?: number }).index
          : undefined;
      if (typeof idx !== "number") return;
      setTurnStatus((prev) => {
        const next = [...prev];
        if (evt.status === "start") next[idx] = "running";
        else if (evt.status === "done") next[idx] = "done";
        else if (evt.status === "error") next[idx] = "error";
        return next;
      });
    } else if (evt.step === "commit") {
      if (evt.status === "start") setCommitStatus("running");
      else if (evt.status === "done") setCommitStatus("done");
    }
    // person + result handled implicitly above.
  };

  const handleSave = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    setTurnStatus(turns.map(() => "pending"));
    setCommitStatus("pending");
    try {
      const personFields =
        selected.kind === "existing"
          ? { person_id: selected.person.person_id }
          : { new_person_name: selected.name };
      const resp = await fetch(
        `${API_BASE}/api/sources/${sourceId}/face-runs/assign`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...personFields,
            segment_ids: turns.map((t) => t.segment_id),
          }),
        },
      );
      if (!resp.ok) {
        const text = await resp.text();
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

  const statusIcon = (s: TurnStatus): string =>
    s === "pending" ? "○" : s === "running" ? "⟳" : s === "done" ? "✓" : "✗";
  const statusColor = (s: TurnStatus): string =>
    s === "pending"
      ? "var(--foreground-ghost)"
      : s === "running"
        ? "var(--accent)"
        : s === "done"
          ? "var(--accent)"
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
            <span style={{ color: "var(--foreground-ghost)" }}>Currently: </span>
            <strong>{run.person_name ?? "?"}</strong>
            {" · "}
            <span style={{ color: "var(--foreground-ghost)" }}>
              {fmtTs(run.start_ts)}–{fmtTs(run.end_ts)} · {run.frame_count} frames ·{" "}
              {turns.length} overlapping turn{turns.length === 1 ? "" : "s"}
            </span>
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
            Saving will reassign all <strong>{turns.length}</strong> overlapping
            speaker turn{turns.length === 1 ? "" : "s"} to{" "}
            <strong>
              {selected.kind === "existing"
                ? selected.person.canonical_name
                : selected.name}
            </strong>
            , write a face embedding from each turn's midpoint, and a voiceprint
            from each turn's audio. Single transaction — partial failures roll
            back the whole batch.
          </div>
        )}

        {submitting && (
          <ul
            className="flex max-h-72 flex-col gap-1 overflow-y-auto rounded border px-3 py-2 text-xs custom-scrollbar"
            style={{
              borderColor: "var(--border)",
              backgroundColor: "var(--background-deep)",
            }}
          >
            {turns.map((t, i) => (
              <li
                key={t.segment_id}
                className="flex items-center gap-2 tabular-nums"
                style={{ color: statusColor(turnStatus[i]) }}
              >
                <span
                  className="inline-block w-4 text-center"
                  style={{
                    animation:
                      turnStatus[i] === "running"
                        ? "spin 1s linear infinite"
                        : undefined,
                  }}
                >
                  {statusIcon(turnStatus[i])}
                </span>
                <span>
                  Turn {i + 1} ({fmtTs(t.start_ts)}–{fmtTs(t.end_ts)})
                  {t.speaker_label ? ` — ${t.speaker_label}` : ""}
                </span>
              </li>
            ))}
            <li
              className="mt-1 flex items-center gap-2 border-t pt-1"
              style={{ color: statusColor(commitStatus), borderColor: "var(--border)" }}
            >
              <span
                className="inline-block w-4 text-center"
                style={{
                  animation:
                    commitStatus === "running" ? "spin 1s linear infinite" : undefined,
                }}
              >
                {statusIcon(commitStatus)}
              </span>
              <span>Commit transaction</span>
            </li>
            <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
          </ul>
        )}

        {error && <p className="text-xs text-red-400">{error}</p>}

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
