"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import type { CrewAgent } from "../round/round-data";

const API_BASE = process.env.NEXT_PUBLIC_API_URL!;

// Fallback data when API is unavailable
const FALLBACK_CREW: CrewAgent[] = [
  { id: "scout", name: "Scout", icon: "\u{1F50D}", status: "dormant", action: null, last_activity: null, next_run: "Tonight 10PM" },
  { id: "scribe", name: "Scribe", icon: "\u270D\uFE0F", status: "dormant", action: null, last_activity: null, next_run: "When Scout finds videos" },
  { id: "analyst", name: "Analyst", icon: "\u{1F9E0}", status: "dormant", action: null, last_activity: null, next_run: "After Scribe finishes" },
  { id: "stats", name: "Stats", icon: "\u{1F4CA}", status: "dormant", action: null, last_activity: null, next_run: "Monday 6AM" },
  { id: "fixtures", name: "Fixtures", icon: "\u{1F3DF}\uFE0F", status: "dormant", action: null, last_activity: null, next_run: "Thursday 6PM" },
];

interface LocalAgent {
  id: string;
  name: string;
  icon: string;
  status: "active" | "queued" | "dormant";
  action: string | null;
  lastAction: string | null;
  nextRun: string | null;
}

function toLocal(a: CrewAgent): LocalAgent {
  return {
    id: a.id,
    name: a.name,
    icon: a.icon,
    status: a.status === "active" ? "active" : "dormant",
    action: a.action,
    lastAction: a.last_activity?.summary ?? null,
    nextRun: a.next_run,
  };
}

function AgentPill({ agent }: { agent: LocalAgent }) {
  return (
    <div
      className="flex items-center gap-2.5 rounded-full border px-1.5 py-1.5 pr-4 text-sm"
      style={{
        borderColor:
          agent.status === "active"
            ? "rgba(245, 130, 32, 0.3)"
            : "var(--color-zinc-800, #27272a)",
        background:
          agent.status === "active"
            ? "rgba(245, 130, 32, 0.04)"
            : "rgba(255, 255, 255, 0.02)",
        animation:
          agent.status === "active"
            ? "crew-pill-pulse 4s ease-in-out infinite"
            : "none",
      }}
    >
      {/* Agent avatar */}
      <div
        className="relative flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm"
        style={{
          background: "rgba(245, 130, 32, 0.12)",
          border: "1.5px solid rgba(245, 130, 32, 0.3)",
          boxShadow:
            agent.status === "active"
              ? "0 0 12px rgba(245, 130, 32, 0.4)"
              : "none",
        }}
      >
        {agent.status === "active" && (
          <span className="absolute -right-0.5 -top-0.5 flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--tigers-orange)] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--tigers-orange)]" />
          </span>
        )}
        <span>{agent.icon}</span>
      </div>

      {/* Status text */}
      <div className="flex flex-col gap-px">
        <span
          className="text-[10px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--tigers-orange)" }}
        >
          {agent.name}
        </span>
        <span className="text-[13px] text-zinc-500">{agent.action}</span>
      </div>
    </div>
  );
}

function DormantAgent({ agent }: { agent: LocalAgent }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className="relative cursor-default"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Label above */}
      <span
        className="absolute -top-1 left-1/2 -translate-x-1/2 -translate-y-full whitespace-nowrap text-[9px] font-medium uppercase tracking-wider transition-opacity duration-200"
        style={{
          color: hovered ? "var(--tigers-orange)" : "transparent",
          opacity: hovered ? 1 : 0,
        }}
      >
        {agent.name}
      </span>

      {/* Avatar */}
      <div
        className="flex h-8 w-8 items-center justify-center rounded-full text-sm transition-all duration-300"
        style={{
          background: hovered
            ? "rgba(245, 130, 32, 0.12)"
            : "rgba(255, 255, 255, 0.04)",
          border: hovered
            ? "1.5px solid rgba(245, 130, 32, 0.3)"
            : "1.5px solid rgba(255, 255, 255, 0.08)",
          opacity: hovered ? 1 : 0.4,
          filter: hovered ? "grayscale(0)" : "grayscale(0.5)",
          transform: hovered ? "scale(1.15)" : "scale(1)",
          boxShadow: hovered
            ? "0 0 12px rgba(245, 130, 32, 0.2)"
            : "none",
        }}
      >
        {!hovered && (
          <span
            className="absolute -right-1 -top-1.5 text-[8px]"
            style={{ opacity: 0.3 }}
          >
            z
          </span>
        )}
        <span>{agent.icon}</span>
      </div>

      {/* Tooltip */}
      {hovered && (
        <div
          className="absolute left-1/2 top-11 z-10 -translate-x-1/2 rounded-lg border px-3 py-2"
          style={{
            background: "#18181b",
            borderColor: "#27272a",
            minWidth: 180,
          }}
        >
          <div
            className="text-[10px] font-medium uppercase tracking-wider"
            style={{ color: "#71717a", marginBottom: 4 }}
          >
            {agent.status === "queued" ? "Queued" : "Dormant"}
          </div>
          {agent.lastAction && (
            <div
              className="text-[11px] leading-relaxed"
              style={{ color: "rgba(255,255,255,0.6)" }}
            >
              {agent.lastAction}
            </div>
          )}
          {agent.nextRun && (
            <div
              className="mt-1 text-[10px]"
              style={{ color: "#3f3f46" }}
            >
              Next: <span style={{ color: "#71717a" }}>{agent.nextRun}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function CrewStatus() {
  const [agents, setAgents] = useState<LocalAgent[]>(FALLBACK_CREW.map(toLocal));
  const [currentRound, setCurrentRound] = useState(0);
  const [currentSeason, setCurrentSeason] = useState(2026);

  useEffect(() => {
    fetch(`${API_BASE}/api/crew/status`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.agents) {
          setAgents(data.agents.map(toLocal));
        }
        if (data?.current_round) {
          setCurrentRound(data.current_round);
        }
        if (data?.current_season) {
          setCurrentSeason(data.current_season);
        }
      })
      .catch(() => {}); // Keep fallback data
  }, []);

  const activeAgents = agents.filter((a) => a.status === "active");
  const dormantAgents = agents.filter(
    (a) => a.status === "dormant" || a.status === "queued",
  );

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Active agent pills */}
      {activeAgents.length > 0 ? (
        <div className="flex flex-col items-center gap-1.5">
          {activeAgents.map((agent) => (
            <AgentPill key={agent.id} agent={agent} />
          ))}
        </div>
      ) : (
        /* Idle state — JeromeLu watching */
        <div
          className="flex items-center gap-2.5 rounded-full border px-1.5 py-1.5 pr-4 text-sm"
          style={{
            borderColor: "#27272a",
            background: "rgba(255, 255, 255, 0.02)",
          }}
        >
          <div
            className="relative flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm"
            style={{
              background: "rgba(245, 130, 32, 0.12)",
              border: "1.5px solid rgba(245, 130, 32, 0.3)",
            }}
          >
            <span className="absolute -right-0.5 -top-0.5 flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--tigers-orange)] opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--tigers-orange)]" />
            </span>
            <span>{"\u{1F440}"}</span>
          </div>
          <span className="text-[13px] text-zinc-500">Watching the market</span>
        </div>
      )}

      {/* Dormant crew row */}
      {dormantAgents.length > 0 && (
        <div className="flex items-center gap-3">
          {dormantAgents.map((agent, i) => (
            <div key={agent.id} className="flex items-center gap-3">
              {i > 0 && (
                <div
                  className="h-[3px] w-[3px] rounded-full"
                  style={{ background: "rgba(255, 255, 255, 0.08)" }}
                />
              )}
              <DormantAgent agent={agent} />
            </div>
          ))}
        </div>
      )}

      {/* Round badge — links to round overview */}
      <Link
        href={`/round/${currentRound || 2}`}
        className="mt-1 rounded-md border px-2.5 py-1 font-mono text-[10px] tracking-wider transition-colors hover:border-[rgba(245,130,32,0.3)] hover:bg-[rgba(245,130,32,0.06)]"
        style={{ borderColor: "#27272a", color: "#52525b" }}
      >
        Round <span style={{ color: "var(--tigers-orange)", fontWeight: 600 }}>{currentRound || 2}</span>
        {" "}&middot; Season {currentSeason}
      </Link>
    </div>
  );
}
