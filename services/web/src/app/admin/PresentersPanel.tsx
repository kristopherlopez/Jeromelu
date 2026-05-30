"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAdminApiBase } from "./apiBase";

interface ChannelRow {
  channel_id: string;
  name: string;
}

interface CoverageResponse {
  per_channel: ChannelRow[];
}

interface Evidence {
  url: string;
  snippet: string;
}

interface PendingCandidate {
  id: string;
  channel_id: string;
  name: string;
  role: string;
  evidence: Evidence[];
  llm_confidence: number | null;
  notes: string | null;
  existing_person_id: string | null;
  status: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  confirmed_person_id: string | null;
  run_id: string | null;
  discovered_at: string;
}

interface ConfirmedPresenter {
  id: string;
  channel_id: string;
  person_id: string;
  person_name: string;
  role: string;
  is_regular: boolean;
  since_ts: string | null;
  confirmed_at: string;
  confirmed_by: string | null;
  candidate_id: string | null;
}

interface ByChannelResponse {
  ok: boolean;
  channel: { channel_id: string; name: string; platform: string; url: string | null };
  confirmed: ConfirmedPresenter[];
  pending: PendingCandidate[];
  rejected: PendingCandidate[];
}

interface RunResponse {
  ok: boolean;
  run_id: string;
  status: string;
  candidates_filed: number;
  duplicates_skipped: number;
  turns_used: number;
  tool_calls: number;
  estimated_cost_usd: number;
  stop_reason: string;
  notes: string[];
}

const ROLE_COLOURS: Record<string, string> = {
  host: "text-emerald-400 border-emerald-700",
  "co-host": "text-emerald-300 border-emerald-800",
  regular: "text-sky-300 border-sky-800",
  "frequent-guest": "text-zinc-400 border-zinc-700",
};

function RoleBadge({ role }: { role: string }) {
  const cls = ROLE_COLOURS[role] ?? "text-zinc-400 border-zinc-700";
  return (
    <span className={`rounded border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${cls}`}>
      {role}
    </span>
  );
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-zinc-600">—</span>;
  const cls =
    value >= 0.8
      ? "text-emerald-400"
      : value >= 0.6
      ? "text-amber-400"
      : "text-zinc-500";
  return <span className={`font-mono text-xs ${cls}`}>{value.toFixed(2)}</span>;
}

export default function PresentersPanel() {
  const { base } = useAdminApiBase();

  const [channels, setChannels] = useState<ChannelRow[]>([]);
  const [channelId, setChannelId] = useState<string>("");
  const [filter, setFilter] = useState("");

  const [data, setData] = useState<ByChannelResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunResponse | null>(null);

  const [pendingActionId, setPendingActionId] = useState<string | null>(null);

  // Populate channel picker from the existing coverage endpoint.
  useEffect(() => {
    fetch(`${base}/api/admin/miner/channel-coverage`)
      .then((r) => r.json())
      .then((j: CoverageResponse) => {
        setChannels(j.per_channel ?? []);
      })
      .catch(() => {});
  }, [base]);

  const fetchByChannel = useCallback(async () => {
    if (!channelId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${base}/api/admin/presenters/by-channel/${channelId}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const j: ByChannelResponse = await r.json();
      setData(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [base, channelId]);

  useEffect(() => {
    setData(null);
    setRunResult(null);
    if (channelId) fetchByChannel();
  }, [channelId, fetchByChannel]);

  const runMiner = useCallback(async () => {
    if (!channelId) return;
    setRunning(true);
    setError(null);
    setRunResult(null);
    try {
      const r = await fetch(
        `${base}/api/admin/presenters/research/${channelId}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
      );
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const j: RunResponse = await r.json();
      setRunResult(j);
      await fetchByChannel();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }, [base, channelId, fetchByChannel]);

  const confirmCandidate = useCallback(
    async (id: string, existingPersonId?: string) => {
      setPendingActionId(id);
      setError(null);
      try {
        const body = existingPersonId
          ? { existing_person_id: existingPersonId, reviewed_by: "admin-ui" }
          : { reviewed_by: "admin-ui" };
        const r = await fetch(
          `${base}/api/admin/presenters/candidates/${id}/confirm`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        );
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        await fetchByChannel();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setPendingActionId(null);
      }
    },
    [base, fetchByChannel],
  );

  const rejectCandidate = useCallback(
    async (id: string) => {
      setPendingActionId(id);
      setError(null);
      try {
        const r = await fetch(
          `${base}/api/admin/presenters/candidates/${id}/reject`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reviewed_by: "admin-ui" }),
          },
        );
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        await fetchByChannel();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setPendingActionId(null);
      }
    },
    [base, fetchByChannel],
  );

  const filteredChannels = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return channels;
    return channels.filter((c) => c.name.toLowerCase().includes(f));
  }, [channels, filter]);

  return (
    <div className="space-y-4">
      {/* Channel picker */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-zinc-300">Channel</span>
          <input
            type="text"
            placeholder="Filter…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-40 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-white"
          />
          <select
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
            className="min-w-[14rem] flex-1 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-white"
          >
            <option value="">— select a channel —</option>
            {filteredChannels.map((c) => (
              <option key={c.channel_id} value={c.channel_id}>
                {c.name}
              </option>
            ))}
          </select>
          <button
            onClick={runMiner}
            disabled={!channelId || running}
            className="rounded bg-orange-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
          >
            {running ? "Researching…" : "Run Presenter Research"}
          </button>
        </div>
        {channelId && data && (
          <div className="mt-2 text-xs text-zinc-500">
            {data.channel.platform} · {data.channel.url ?? "no url"}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {runResult && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-3 text-xs text-zinc-400">
          <span className="font-medium text-zinc-200">Run {runResult.status}</span>
          {" — "}
          filed {runResult.candidates_filed}, dupes {runResult.duplicates_skipped}, turns{" "}
          {runResult.turns_used}, ${runResult.estimated_cost_usd.toFixed(3)}
          {runResult.notes.length > 0 && (
            <span className="text-amber-400"> · {runResult.notes.join(" / ")}</span>
          )}
        </div>
      )}

      {/* Confirmed presenters */}
      {data && data.confirmed.length > 0 && (
        <div className="rounded-lg border border-zinc-800">
          <div className="border-b border-zinc-800 px-4 py-2 text-sm font-medium text-zinc-300">
            Confirmed presenters ({data.confirmed.length})
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Role</th>
                <th className="px-3 py-2">Confirmed</th>
                <th className="px-3 py-2">By</th>
              </tr>
            </thead>
            <tbody>
              {data.confirmed.map((p) => (
                <tr key={p.id} className="border-b border-zinc-800/50">
                  <td className="px-3 py-2 text-zinc-200">{p.person_name}</td>
                  <td className="px-3 py-2"><RoleBadge role={p.role} /></td>
                  <td className="px-3 py-2 text-zinc-500">
                    {new Date(p.confirmed_at).toLocaleString("en-AU", { dateStyle: "short", timeStyle: "short" })}
                  </td>
                  <td className="px-3 py-2 text-zinc-500">{p.confirmed_by ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pending candidates */}
      {data && (
        <div className="rounded-lg border border-zinc-800">
          <div className="border-b border-zinc-800 px-4 py-2 text-sm font-medium text-zinc-300">
            Pending review ({data.pending.length})
          </div>
          {data.pending.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-zinc-600">
              {loading ? "Loading…" : "No pending candidates. Run the agent to file some."}
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {data.pending.map((c) => (
                <div key={c.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-base font-medium text-zinc-100">{c.name}</span>
                    <RoleBadge role={c.role} />
                    <ConfidenceBadge value={c.llm_confidence} />
                    {c.existing_person_id && (
                      <span className="rounded border border-amber-800 px-2 py-0.5 text-[10px] uppercase tracking-wider text-amber-400">
                        existing person hint
                      </span>
                    )}
                    <div className="ml-auto flex gap-2">
                      <button
                        onClick={() =>
                          confirmCandidate(c.id, c.existing_person_id ?? undefined)
                        }
                        disabled={pendingActionId === c.id}
                        className="rounded bg-emerald-700 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
                        title={
                          c.existing_person_id
                            ? "Confirm and link to existing person"
                            : "Confirm — creates a new Person"
                        }
                      >
                        {c.existing_person_id ? "Confirm + link" : "Confirm"}
                      </button>
                      <button
                        onClick={() => rejectCandidate(c.id)}
                        disabled={pendingActionId === c.id}
                        className="rounded bg-zinc-800 px-3 py-1 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </div>

                  {c.evidence.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {c.evidence.map((e, i) => (
                        <li key={i} className="text-xs">
                          <a
                            href={e.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-orange-400 hover:underline"
                          >
                            {e.url.replace(/^https?:\/\//, "")}
                          </a>
                          <span className="ml-2 text-zinc-400">— “{e.snippet}”</span>
                        </li>
                      ))}
                    </ul>
                  )}

                  {c.notes && (
                    <div className="mt-1 text-xs italic text-zinc-500">{c.notes}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Rejected — collapsed by default; useful as a sanity check */}
      {data && data.rejected.length > 0 && (
        <details className="rounded-lg border border-zinc-800">
          <summary className="cursor-pointer px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200">
            Recently rejected ({data.rejected.length})
          </summary>
          <ul className="divide-y divide-zinc-800/50">
            {data.rejected.map((c) => (
              <li key={c.id} className="px-4 py-2 text-sm">
                <span className="text-zinc-300">{c.name}</span>
                <span className="ml-2 text-xs text-zinc-500">{c.role}</span>
                {c.reviewed_at && (
                  <span className="ml-2 text-xs text-zinc-600">
                    {new Date(c.reviewed_at).toLocaleString("en-AU", { dateStyle: "short" })}
                  </span>
                )}
                {c.notes && <span className="ml-2 text-xs italic text-zinc-500">{c.notes}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
