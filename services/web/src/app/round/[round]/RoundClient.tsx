"use client";

import { useRouter } from "next/navigation";
import type {
  RoundOverviewResponse,
  ConsensusPlayer,
  ActivityLogEntry,
} from "../round-data";

const AGENT_ICONS: Record<string, string> = {
  scout: "\u{1F50D}",
  scribe: "\u270D\uFE0F",
  analyst: "\u{1F9E0}",
  stats: "\u{1F4CA}",
  fixtures: "\u{1F3DF}\uFE0F",
};

function StatusBadge({ status }: { status: string }) {
  if (status === "complete") {
    return (
      <span className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider"
        style={{ color: "rgb(80, 200, 120)", background: "rgba(80, 200, 120, 0.12)", border: "1px solid rgba(80, 200, 120, 0.25)" }}>
        &#x2713; Complete
      </span>
    );
  }
  if (status === "in_progress") {
    return (
      <span className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider"
        style={{ color: "var(--tigers-orange)", background: "rgba(245,130,32,0.12)", border: "1px solid rgba(245,130,32,0.3)" }}>
        In Progress
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider text-zinc-600"
      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid #27272a" }}>
      Pending
    </span>
  );
}

function CrewChips({ crew }: { crew: RoundOverviewResponse["crew_summary"] }) {
  const chipOrder = ["fixtures", "scout", "scribe", "analyst", "stats"];
  const labels: Record<string, string> = {
    fixtures: "Team Lists",
    scout: "Sources",
    scribe: "Cleaned",
    analyst: "Analysed",
    stats: "Scored",
  };

  return (
    <div className="flex flex-wrap gap-2">
      {chipOrder.map((agentId) => {
        const data = crew[agentId];
        const done = data && data.completed > 0;
        return (
          <div key={agentId}
            className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] text-zinc-500"
            style={{ background: "rgba(255,255,255,0.03)", borderColor: "#27272a" }}>
            <span className="text-[13px]">{AGENT_ICONS[agentId]}</span>
            <span>{labels[agentId] || data?.name || agentId}</span>
            {done && <span style={{ color: "rgb(80, 200, 120)", fontSize: 10 }}>&#x2713;</span>}
          </div>
        );
      })}
    </div>
  );
}

function SignalCard({ signal }: { signal: RoundOverviewResponse["signal"] }) {
  if (signal.total_claims === 0) return null;

  return (
    <div className="rounded-xl border p-4"
      style={{ background: "rgba(245,130,32,0.06)", borderColor: "rgba(245,130,32,0.15)", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: "var(--tigers-orange)", borderRadius: "3px 0 0 3px" }} />
      <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--tigers-orange)" }}>
        &#x26A1; Round Summary
      </div>
      <div className="text-sm text-zinc-400">
        {signal.total_claims} claims extracted &mdash;{" "}
        {signal.buy > 0 && <span style={{ color: "rgb(80, 200, 120)" }}>{signal.buy} buy</span>}
        {signal.sell > 0 && <>, <span style={{ color: "rgb(239, 68, 68)" }}>{signal.sell} sell</span></>}
        {signal.hold > 0 && <>, {signal.hold} hold</>}
        {signal.captain > 0 && <>, <span style={{ color: "var(--tigers-orange)" }}>{signal.captain} captain</span></>}
        {signal.avoid > 0 && <>, {signal.avoid} avoid</>}
        {signal.breakout > 0 && <>, {signal.breakout} breakout</>}
      </div>
    </div>
  );
}

function ConsensusGrid({ consensus }: { consensus: ConsensusPlayer[] }) {
  if (consensus.length === 0) {
    return <p className="text-sm text-zinc-600">No claims for this round yet.</p>;
  }

  const buys = consensus.filter((p) => p.buy > 0).sort((a, b) => b.buy - a.buy).slice(0, 5);
  const sells = consensus.filter((p) => p.sell > 0 || p.avoid > 0).sort((a, b) => (b.sell + b.avoid) - (a.sell + a.avoid)).slice(0, 5);
  const captains = consensus.filter((p) => p.captain > 0).sort((a, b) => b.captain - a.captain).slice(0, 4);
  const holds = consensus.filter((p) => p.hold > 0).sort((a, b) => b.hold - a.hold).slice(0, 4);

  return (
    <div className="grid grid-cols-2 gap-2">
      <ConsensusCard title="Strong Buy" icon="&#x2191;" color="rgb(80, 200, 120)" players={buys} field="buy" />
      <ConsensusCard title="Strong Sell" icon="&#x2193;" color="rgb(239, 68, 68)" players={sells} field="sell" />
      <ConsensusCard title="Captain Picks" icon="&#x1F451;" color="var(--tigers-orange)" players={captains} field="captain" />
      <ConsensusCard title="Hold" icon="&#x1F440;" color="rgb(96, 165, 250)" players={holds} field="hold" />
    </div>
  );
}

function ConsensusCard({
  title, icon, color, players, field,
}: {
  title: string; icon: string; color: string;
  players: ConsensusPlayer[]; field: keyof ConsensusPlayer;
}) {
  if (players.length === 0) return <div className="rounded-xl border border-zinc-800 p-3.5" style={{ background: "rgba(255,255,255,0.02)" }} />;

  const maxCount = Math.max(...players.map((p) => (p[field] as number) || 0), 1);

  return (
    <div className="rounded-xl border border-zinc-800 p-3.5" style={{ background: "rgba(255,255,255,0.02)" }}>
      <h3 className="mb-2.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider"
        style={{ color }} dangerouslySetInnerHTML={{ __html: `${icon} ${title}` }} />
      {players.map((p) => {
        const count = (p[field] as number) || 0;
        const pct = (count / maxCount) * 100;
        return (
          <div key={p.entity_id} className="flex items-center gap-2 py-1">
            <span className="flex-1 text-[13px] font-medium text-zinc-200">{p.name}</span>
            <div className="h-1 w-14 overflow-hidden rounded-full" style={{ background: "#27272a" }}>
              <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
            </div>
            <span className="w-6 text-right font-mono text-[10px] text-zinc-500">{count}</span>
          </div>
        );
      })}
    </div>
  );
}

function SourcesList({ sources }: { sources: RoundOverviewResponse["sources"] }) {
  if (sources.length === 0) {
    return <p className="text-sm text-zinc-600">No sources analysed for this round yet.</p>;
  }

  return (
    <div className="flex flex-col gap-1.5">
      {sources.map((s) => (
        <div key={s.source_id}
          className="flex items-center gap-3 rounded-xl border border-zinc-800 px-3.5 py-2.5 transition-colors hover:border-[rgba(245,130,32,0.3)] hover:bg-[rgba(245,130,32,0.06)]"
          style={{ background: "rgba(255,255,255,0.02)" }}>
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg"
            style={{ background: "#18181b" }}>&#x25B6;</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-zinc-200">{s.title}</div>
            {s.creator_name && <div className="mt-0.5 text-[11px] text-zinc-600">{s.creator_name}</div>}
          </div>
          <div className="text-center">
            <div className="font-mono text-sm font-semibold" style={{ color: "var(--tigers-orange)" }}>{s.claim_count}</div>
            <div className="text-[9px] uppercase tracking-wider text-zinc-600">Claims</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ActivityLog({ entries }: { entries: ActivityLogEntry[] }) {
  if (entries.length === 0) {
    return <p className="text-sm text-zinc-600">No crew activity for this round yet.</p>;
  }

  function formatTime(iso: string) {
    const d = new Date(iso);
    const day = d.toLocaleDateString("en-AU", { weekday: "short" });
    const time = d.toLocaleTimeString("en-AU", { hour: "numeric", minute: "2-digit", hour12: true });
    return `${day} ${time}`;
  }

  return (
    <div className="flex flex-col">
      {entries.map((e) => (
        <div key={e.activity_id} className="flex items-start gap-2.5 border-b border-zinc-800/50 py-2 last:border-b-0">
          <span className="w-[60px] shrink-0 pt-0.5 font-mono text-[10px] text-zinc-700">
            {formatTime(e.created_at)}
          </span>
          <div className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-md text-[11px]"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid #27272a" }}>
            {AGENT_ICONS[e.agent_id] || "?"}
          </div>
          <div className="text-[12px] text-zinc-500">
            <strong className="font-medium text-zinc-400">{e.agent_name}</strong>{" "}
            {e.summary}
          </div>
        </div>
      ))}
    </div>
  );
}

function SectionHeader({ icon, title, detail }: { icon: string; title: string; detail?: string }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <div className="flex h-7 w-7 items-center justify-center rounded-lg text-sm"
        style={{ background: "rgba(245,130,32,0.12)", border: "1px solid rgba(245,130,32,0.15)" }}>
        {icon}
      </div>
      <h2 className="text-sm font-semibold text-zinc-200">{title}</h2>
      {detail && <span className="ml-auto font-mono text-[10px] text-zinc-600">{detail}</span>}
    </div>
  );
}

export default function RoundClient({ data }: { data: RoundOverviewResponse }) {
  const router = useRouter();

  return (
    <div className="mx-auto max-w-[720px] px-6 py-10">
      {/* Header */}
      <div className="mb-8 flex items-center gap-4">
        <button onClick={() => router.push("/")}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 text-sm text-zinc-500 transition-colors hover:border-[rgba(245,130,32,0.3)] hover:text-[var(--tigers-orange)]"
          style={{ background: "rgba(255,255,255,0.04)" }}>
          &#x2190;
        </button>
        <div>
          <h1 className="text-2xl font-bold">
            Round <span style={{ color: "var(--tigers-orange)" }}>{data.round}</span>
          </h1>
          <p className="text-[13px] text-zinc-500">Season {data.season}</p>
        </div>
        <div className="ml-auto">
          <StatusBadge status={data.status} />
        </div>
      </div>

      {/* Crew chips */}
      <div className="mb-8">
        <CrewChips crew={data.crew_summary} />
      </div>

      {/* Signal card */}
      <div className="mb-8">
        <SignalCard signal={data.signal} />
      </div>

      {/* Consensus */}
      <div className="mb-8">
        <SectionHeader icon="&#x1F4CA;" title="Consensus" detail={`${data.consensus.length} players`} />
        <ConsensusGrid consensus={data.consensus} />
      </div>

      {/* Sources */}
      <div className="mb-8">
        <SectionHeader icon="&#x1F9E0;" title="Sources Analysed" detail={`${data.sources.length} videos`} />
        <SourcesList sources={data.sources} />
      </div>

      {/* Activity log */}
      <div className="mb-8">
        <SectionHeader icon="&#x1F4DD;" title="Crew Activity" detail="this round" />
        <ActivityLog entries={data.activity_log} />
      </div>
    </div>
  );
}
