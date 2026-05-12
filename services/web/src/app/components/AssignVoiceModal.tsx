"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { API_BASE } from "@/lib/api";
import type { PersonSummary, VoiceCluster } from "@/lib/types";
import PersonPicker from "./PersonPicker";

interface Props {
  sourceId: string;
  cluster: VoiceCluster;
  onClose: () => void;
  onSaved: () => void;
}

type Selection =
  | { kind: "existing"; person: PersonSummary }
  | { kind: "new"; name: string };

type PhaseStatus = "pending" | "running" | "done" | "skip" | "error";

/** The streamed phases emitted by /voice-clusters/{label}/assign. Mirror
 *  shape of AssignRunModal (face cluster assign) — the framing person/result
 *  events bracket a fixed three-row phase checklist. */
type Phase = "voice_enrol" | "attribute" | "commit";

interface StreamEvent {
  step: "person" | Phase | "result" | "unknown";
  status: "start" | "done" | "skip" | "error";
  detail?: unknown;
}

const PHASE_LABELS: Record<Phase, string> = {
  voice_enrol: "Promote voiceprint exemplars from cluster",
  attribute: "Attribute speaker turns to person",
  commit: "Commit transaction",
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

export default function AssignVoiceModal({
  sourceId,
  cluster,
  onClose,
  onSaved,
}: Props) {
  const [selected, setSelected] = useState<Selection | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [phases, setPhases] = useState<Record<Phase, PhaseStatus>>({
    voice_enrol: "pending",
    attribute: "pending",
    commit: "pending",
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
      console.error(
        "[assign-voice-cluster] stream error:",
        { step: evt.step, status: evt.status, detail: evt.detail },
      );
      setError(detail);
      if (
        evt.step === "voice_enrol" ||
        evt.step === "attribute" ||
        evt.step === "commit"
      ) {
        setPhases((prev) => ({ ...prev, [evt.step as Phase]: "error" }));
      }
      return;
    }

    if (
      evt.step === "voice_enrol" ||
      evt.step === "attribute" ||
      evt.step === "commit"
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
    // person + result events handled implicitly.
  };

  const handleSave = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    setPhases({
      voice_enrol: "pending",
      attribute: "pending",
      commit: "pending",
    });
    try {
      const personFields =
        selected.kind === "existing"
          ? { person_id: selected.person.person_id }
          : { new_person_name: selected.name };
      const resp = await fetch(
        `${API_BASE}/api/sources/${sourceId}/voice-clusters/${encodeURIComponent(cluster.speaker_label)}/assign`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(personFields),
        },
      );
      if (!resp.ok) {
        const text = await resp.text();
        console.error("[assign-voice-cluster] HTTP error:", {
          status: resp.status,
          body: text,
        });
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
            console.error("assign-voice: bad line", line);
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

  const eligible = cluster.embedding_eligible_count;
  const firstTs = cluster.first_ts;
  const lastTs = cluster.last_ts;

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
          Assign voice cluster
        </h2>
        <div
          className="rounded border px-3 py-2 text-xs"
          style={{
            borderColor: "var(--border)",
            backgroundColor: "var(--background-deep)",
          }}
        >
          <div>
            <strong>{cluster.speaker_label}</strong>
            {" · "}
            <span style={{ color: "var(--foreground-ghost)" }}>
              Currently: {cluster.dominant_person_name ?? "Unattributed"}
            </span>
          </div>
          <div style={{ color: "var(--foreground-ghost)" }}>
            {cluster.turn_count.toLocaleString()} turn
            {cluster.turn_count === 1 ? "" : "s"} ·{" "}
            {fmtTs(firstTs)}–{fmtTs(lastTs)} ·{" "}
            {eligible} eligible for voiceprint enrolment
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
            Saving will attribute all <strong>{cluster.turn_count}</strong>{" "}
            turn{cluster.turn_count === 1 ? "" : "s"} labelled{" "}
            <strong>{cluster.speaker_label}</strong> to{" "}
            <strong>
              {selected.kind === "existing"
                ? selected.person.canonical_name
                : selected.name}
            </strong>
            {eligible > 0 ? (
              <>
                {" "}and promote up to <strong>{Math.min(eligible, 10)}</strong>{" "}
                medoid voiceprints from the cluster's longest turns into the
                voice registry.
              </>
            ) : (
              <>
                . No voiceprints will be written — all turns in this cluster
                are sub-300ms with NULL embeddings.
              </>
            )}
            {" "}Single transaction — partial failures roll back the whole
            batch.
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
                  key: "voice_enrol" as Phase,
                  label: PHASE_LABELS.voice_enrol,
                },
                {
                  key: "attribute" as Phase,
                  label: `Attribute ${cluster.turn_count} turn${cluster.turn_count === 1 ? "" : "s"} to person`,
                },
                {
                  key: "commit" as Phase,
                  label: PHASE_LABELS.commit,
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
            style={{
              borderColor: "var(--border)",
              color: "var(--foreground-secondary)",
            }}
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
            {submitting ? "Assigning…" : "Assign cluster"}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body);
}
