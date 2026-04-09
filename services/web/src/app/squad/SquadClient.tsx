"use client";

import { useState } from "react";
import type {
  SquadResponse,
  SquadSlot,
  CaptainPick,
  TradeEntry,
  SquadPlan,
} from "./squad-data";

/* ── NRL field position mapping ─────────────────────────────────── */

// SuperCoach positions → NRL jersey numbers and field coordinates.
// Coordinates are percentages: x = across field (0=left touchline, 100=right),
//                              y = down field (0=own dead ball, 100=opposition dead ball)
//
// Jersey assignment order per position group:
//   FLB → jersey 1 (fullback)
//   CTW → jerseys 2(RW), 3(RC), 4(LC), 5(LW) — wings wide, centres inside
//   5/8 → jersey 6
//   HFB → jersey 7
//   FRF → jerseys 8, 10 (props)
//   HOK → jersey 9
//   2RF → jerseys 11, 12, 13 (second row + lock)

interface FieldPlacement {
  jersey: number;
  label: string;
  x: number; // % from left
  y: number; // % from top (own try line = ~5%, halfway = 50%)
}

// NRL field positions — own try line at top, attacking downward
const JERSEY_PLACEMENTS: Record<number, { label: string; x: number; y: number }> = {
  1:  { label: "FB",  x: 50, y: 10 },   // Fullback — 10m, centred
  2:  { label: "RW",  x: 85, y: 15 },   // Right Wing — 10m, near right touchline
  5:  { label: "LW",  x: 15, y: 15 },   // Left Wing — 10m, near left touchline
  3:  { label: "RC",  x: 70, y: 25 },   // Right Centre — 20m, inside right wing
  4:  { label: "LC",  x: 30, y: 25 },   // Left Centre — 20m, inside left wing
  6:  { label: "5/8", x: 38, y: 38 },   // Five-eighth — 30m, left of centre
  7:  { label: "HFB", x: 62, y: 38 },   // Halfback — 30m, right of centre
  9:  { label: "HOK", x: 50, y: 52 },   // Hooker — halfway, centred (at the ruck)
  11: { label: "2RF", x: 25, y: 56 },   // Left Second Row — halfway, left edge
  13: { label: "LK",  x: 50, y: 60 },   // Lock — just past halfway, centre
  12: { label: "2RF", x: 75, y: 56 },   // Right Second Row — halfway, right edge
  8:  { label: "FRF", x: 40, y: 68 },   // Left Prop — 40m, left of centre
  10: { label: "FRF", x: 60, y: 68 },   // Right Prop — 40m, right of centre
};

function assignJerseys(slots: SquadSlot[]): (SquadSlot & FieldPlacement)[] {
  const result: (SquadSlot & FieldPlacement)[] = [];

  // Group by SC position
  const byPos: Record<string, SquadSlot[]> = {};
  for (const s of slots) {
    (byPos[s.position] ??= []).push(s);
  }

  // FLB → jersey 1
  const flbs = byPos["FLB"] ?? [];
  if (flbs[0]) result.push({ ...flbs[0], ...JERSEY_PLACEMENTS[1], jersey: 1 });

  // CTW → jerseys 2, 5 (wings), then 3, 4 (centres)
  const ctws = byPos["CTW"] ?? [];
  const ctwJerseys = [2, 5, 3, 4];
  ctws.forEach((s, i) => {
    if (i < ctwJerseys.length) {
      const j = ctwJerseys[i];
      result.push({ ...s, ...JERSEY_PLACEMENTS[j], jersey: j });
    }
  });

  // 5/8 → jersey 6
  const fiveEighths = byPos["5/8"] ?? [];
  if (fiveEighths[0]) result.push({ ...fiveEighths[0], ...JERSEY_PLACEMENTS[6], jersey: 6 });

  // HFB → jersey 7
  const halfs = byPos["HFB"] ?? [];
  if (halfs[0]) result.push({ ...halfs[0], ...JERSEY_PLACEMENTS[7], jersey: 7 });

  // HOK → jersey 9
  const hookers = byPos["HOK"] ?? [];
  if (hookers[0]) result.push({ ...hookers[0], ...JERSEY_PLACEMENTS[9], jersey: 9 });

  // FRF → jerseys 8, 10
  const props = byPos["FRF"] ?? [];
  const frfJerseys = [8, 10];
  props.forEach((s, i) => {
    if (i < frfJerseys.length) {
      const j = frfJerseys[i];
      result.push({ ...s, ...JERSEY_PLACEMENTS[j], jersey: j });
    }
  });

  // 2RF → jerseys 11, 12, then 13 (lock)
  const secondRow = byPos["2RF"] ?? [];
  const srfJerseys = [11, 12, 13];
  secondRow.forEach((s, i) => {
    if (i < srfJerseys.length) {
      const j = srfJerseys[i];
      result.push({ ...s, ...JERSEY_PLACEMENTS[j], jersey: j });
    }
  });

  return result;
}

/* ── Small helpers ─────────────────────────────────────────────── */

function ConvictionMeter({ level }: { level: string }) {
  const bars = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const color =
    level === "high"
      ? "var(--accent)"
      : level === "medium"
        ? "var(--accent-glow)"
        : "var(--accent-glow)";

  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-2 w-1.5 rounded-sm"
          style={{
            background: i <= bars ? color : "var(--border)",
          }}
        />
      ))}
      <span
        className="ml-1 text-[9px] font-semibold uppercase tracking-wider"
        style={{ color }}
      >
        {level}
      </span>
    </div>
  );
}

function PriceChange({ change }: { change: number | null }) {
  if (change === null || change === 0) return null;
  if (change > 0) {
    return (
      <span style={{ color: "rgb(80, 200, 120)" }}>
        +${(change / 1000).toFixed(0)}k
      </span>
    );
  }
  return (
    <span style={{ color: "rgb(239, 68, 68)" }}>
      -${(Math.abs(change) / 1000).toFixed(0)}k
    </span>
  );
}

/* ── Field player pip ──────────────────────────────────────────── */

function FieldPip({
  slot,
  jersey,
  posLabel,
  onSelect,
  isSelected,
}: {
  slot: SquadSlot;
  jersey: number;
  posLabel: string;
  onSelect: (s: SquadSlot) => void;
  isSelected: boolean;
}) {
  const { player } = slot;

  // Surname only for compact display
  const parts = player.name.split(" ");
  const surname = parts.length > 1 ? parts.slice(1).join(" ") : parts[0];

  return (
    <button
      onClick={() => onSelect(slot)}
      className="flex flex-col items-center gap-0.5 focus:outline-none"
      style={{ position: "absolute", transform: "translate(-50%, -50%)" }}
    >
      {/* Jersey circle */}
      <div
        className="relative flex h-10 w-10 items-center justify-center rounded-full text-[12px] font-bold transition-all duration-200"
        style={{
          background: isSelected
            ? "var(--accent-border)"
            : "var(--border)",
          border: isSelected
            ? "2px solid var(--accent)"
            : slot.is_captain
              ? "2px solid var(--accent-glow)"
              : "2px solid var(--border-subtle)",
          boxShadow: isSelected
            ? "0 0 16px var(--accent-glow)"
            : slot.is_captain
              ? "0 0 12px var(--accent-border)"
              : "none",
          color: isSelected ? "var(--accent)" : "var(--foreground)",
        }}
      >
        {jersey}
        {slot.is_captain && (
          <span
            className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full text-[8px] font-black"
            style={{ background: "var(--accent)", color: "#000" }}
          >
            C
          </span>
        )}
        {slot.is_vice_captain && (
          <span
            className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full text-[7px] font-bold"
            style={{
              background: "var(--border-subtle)",
              color: "var(--foreground-secondary)",
              border: "1px solid var(--border)",
            }}
          >
            VC
          </span>
        )}
      </div>

      {/* Name */}
      <span
        className="text-[10px] font-semibold leading-tight whitespace-nowrap"
        style={{ color: isSelected ? "var(--accent)" : "var(--foreground)" }}
      >
        {surname}
      </span>

      {/* Position label */}
      <span className="text-[8px] font-medium uppercase tracking-wider text-zinc-600">
        {posLabel}
      </span>
    </button>
  );
}

/* ── Player detail panel (shown when pip is tapped) ────────────── */

function PlayerDetail({ slot }: { slot: SquadSlot }) {
  const { player } = slot;

  return (
    <div
      className="rounded-xl border p-4"
      style={{
        background: slot.is_captain
          ? "var(--accent-bg)"
          : "rgba(255, 255, 255, 0.03)",
        borderColor: slot.is_captain
          ? "var(--accent-border)"
          : "var(--border)",
      }}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-bold text-zinc-100">
              {player.name}
            </span>
            {slot.is_captain && (
              <span
                className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase"
                style={{
                  background: "var(--accent-border)",
                  color: "var(--accent)",
                }}
              >
                Captain
              </span>
            )}
            {slot.is_vice_captain && (
              <span className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase text-zinc-500"
                style={{ background: "var(--border)" }}>
                Vice Captain
              </span>
            )}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-zinc-500">
            <span>{slot.position}</span>
            {player.team && (
              <>
                <span className="text-zinc-700">&middot;</span>
                <span>{player.team}</span>
              </>
            )}
          </div>
        </div>
        <ConvictionMeter level={slot.conviction} />
      </div>

      {/* Stats grid */}
      <div className="mt-3 flex gap-4">
        {player.price !== null && (
          <div>
            <div className="text-[9px] uppercase tracking-wider text-zinc-600">
              Price
            </div>
            <div className="font-mono text-[14px] font-semibold text-zinc-200">
              ${(player.price / 1000).toFixed(0)}k
            </div>
            <div className="text-[10px]">
              <PriceChange change={player.price_change} />
            </div>
          </div>
        )}
        {player.avg_score !== null && (
          <div>
            <div className="text-[9px] uppercase tracking-wider text-zinc-600">
              Avg
            </div>
            <div className="font-mono text-[14px] font-semibold text-zinc-200">
              {player.avg_score.toFixed(0)}
            </div>
          </div>
        )}
        {player.last_score !== null && (
          <div>
            <div className="text-[9px] uppercase tracking-wider text-zinc-600">
              Last
            </div>
            <div className="font-mono text-[14px] font-semibold text-zinc-200">
              {player.last_score}
            </div>
          </div>
        )}
      </div>

      {/* Rationale */}
      {slot.rationale && (
        <p className="mt-3 text-[12px] leading-relaxed text-zinc-400">
          &ldquo;{slot.rationale}&rdquo;
        </p>
      )}
    </div>
  );
}

/* ── The field ─────────────────────────────────────────────────── */

function FieldLayout({
  starting,
  selectedSlot,
  onSelect,
}: {
  starting: SquadSlot[];
  selectedSlot: SquadSlot | null;
  onSelect: (s: SquadSlot) => void;
}) {
  const placements = assignJerseys(starting);
  const selectedIndex = selectedSlot?.slot_index ?? null;

  return (
    <div
      className="relative overflow-hidden rounded-2xl border"
      style={{
        borderColor: "rgba(40, 80, 40, 0.4)",
        background:
          "linear-gradient(180deg, #0a1f0a 0%, #0f2d0f 20%, #122e12 40%, #0f2d0f 60%, #0a1f0a 100%)",
        /* Fixed aspect ratio roughly matching NRL field proportions (100m × 68m ≈ 1.47:1) */
        aspectRatio: "68 / 100",
      }}
    >
      {/* NRL field markings — 10m intervals, 40m lines red, try lines, dead ball */}
      <div className="pointer-events-none absolute inset-0">
        {/* Dead ball areas (darker zones beyond try lines) */}
        <div
          className="absolute left-0 right-0 top-0"
          style={{ height: "4%", background: "rgba(0, 0, 0, 0.3)" }}
        />
        <div
          className="absolute left-0 right-0 bottom-0"
          style={{ height: "4%", background: "rgba(0, 0, 0, 0.3)" }}
        />

        {/* Try lines (goal lines) — thick white */}
        {[4, 96].map((pct) => (
          <div
            key={`try-${pct}`}
            className="absolute left-[6%] right-[6%]"
            style={{ top: `${pct}%`, height: 2, background: "rgba(255, 255, 255, 0.12)" }}
          />
        ))}

        {/* Touchlines (sidelines) */}
        {[6, 94].map((pct) => (
          <div
            key={`touch-${pct}`}
            className="absolute"
            style={{
              left: `${pct}%`,
              top: "4%",
              bottom: "4%",
              width: 1,
              background: "rgba(255, 255, 255, 0.08)",
            }}
          />
        ))}

        {/*
          10m transverse lines between try lines
          Try line = 0m, halfway = 50m
          Lines at: 10, 20, 30, 40, 50, 40, 30, 20, 10
          Map to percentages of the playing area (4% to 96% = 92% span)
          Each 10m = 9.2% of total height
        */}
        {[
          { m: 10, pct: 4 + 9.2 * 1, red: false, label: "10" },
          { m: 20, pct: 4 + 9.2 * 2, red: false, label: "20" },
          { m: 30, pct: 4 + 9.2 * 3, red: false, label: "30" },
          { m: 40, pct: 4 + 9.2 * 4, red: true, label: "40" },
          { m: 50, pct: 50, red: false, label: "50" },
          { m: 40, pct: 96 - 9.2 * 4, red: true, label: "40" },
          { m: 30, pct: 96 - 9.2 * 3, red: false, label: "30" },
          { m: 20, pct: 96 - 9.2 * 2, red: false, label: "20" },
          { m: 10, pct: 96 - 9.2 * 1, red: false, label: "10" },
        ].map((line, i) => (
          <div key={`line-${i}`}>
            {/* Transverse line */}
            <div
              className="absolute left-[6%] right-[6%]"
              style={{
                top: `${line.pct}%`,
                height: line.label === "50" ? 2 : 1,
                background: line.red
                  ? "rgba(200, 50, 50, 0.12)"
                  : "rgba(255, 255, 255, 0.07)",
              }}
            />
            {/* Distance marker */}
            <div
              className="absolute text-[7px] font-mono font-bold"
              style={{
                top: `${line.pct}%`,
                left: "7%",
                transform: "translateY(-50%)",
                color: line.red
                  ? "rgba(200, 50, 50, 0.15)"
                  : "rgba(255, 255, 255, 0.08)",
              }}
            >
              {line.label}
            </div>
          </div>
        ))}

        {/* Dashed lines 10m from each touchline (parallel to sidelines) */}
        {[16, 84].map((pct) => (
          <div
            key={`dash-${pct}`}
            className="absolute"
            style={{
              left: `${pct}%`,
              top: "4%",
              bottom: "4%",
              width: 1,
              background:
                "repeating-linear-gradient(to bottom, rgba(255,255,255,0.06) 0px, rgba(255,255,255,0.06) 6px, transparent 6px, transparent 12px)",
            }}
          />
        ))}
      </div>

      {/* Players — absolutely positioned on the field */}
      <div className="absolute inset-0">
        {placements.map((p) => (
          <div
            key={p.jersey}
            style={{ position: "absolute", left: `${p.x}%`, top: `${p.y}%` }}
          >
            <FieldPip
              slot={p}
              jersey={p.jersey}
              posLabel={p.label}
              onSelect={onSelect}
              isSelected={selectedIndex === p.slot_index}
            />
          </div>
        ))}
      </div>

      {/* Attack direction indicator */}
      <div
        className="absolute bottom-2 left-1/2 flex -translate-x-1/2 items-center gap-1 text-[8px] uppercase tracking-widest"
        style={{ color: "var(--foreground-ghost)" }}
      >
        <span>&darr;</span>
        <span>Attack</span>
        <span>&darr;</span>
      </div>
    </div>
  );
}

/* ── Bench row ─────────────────────────────────────────────────── */

function BenchCard({ slot, onSelect, isSelected }: {
  slot: SquadSlot;
  onSelect: (s: SquadSlot) => void;
  isSelected: boolean;
}) {
  const { player } = slot;

  return (
    <button
      onClick={() => onSelect(slot)}
      className="flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left transition-colors"
      style={{
        background: isSelected
          ? "var(--accent-bg)"
          : "rgba(255, 255, 255, 0.02)",
        borderColor: isSelected
          ? "var(--accent-border)"
          : "var(--border)",
      }}
    >
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
        style={{
          background: isSelected
            ? "var(--accent-border)"
            : "var(--border)",
          border: isSelected
            ? "1.5px solid var(--accent-glow)"
            : "1.5px solid var(--border)",
          color: isSelected ? "var(--accent)" : "var(--foreground-secondary)",
        }}
      >
        {slot.slot_index}
      </div>
      <span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-600 w-7">
        {slot.position}
      </span>
      <div className="min-w-0 flex-1">
        <div
          className="text-[12px] font-medium truncate"
          style={{ color: isSelected ? "var(--accent)" : "var(--foreground)" }}
        >
          {player.name}
        </div>
        {player.team && (
          <div className="text-[10px] text-zinc-600">{player.team}</div>
        )}
      </div>
      <div className="text-right">
        {player.price !== null && (
          <div className="font-mono text-[11px] text-zinc-400">
            ${(player.price / 1000).toFixed(0)}k
          </div>
        )}
        <div className="text-[10px]">
          <PriceChange change={player.price_change} />
        </div>
      </div>
    </button>
  );
}

/* ── Captain card ──────────────────────────────────────────────── */

function CaptainCard({ captain }: { captain: CaptainPick }) {
  return (
    <div
      className="rounded-xl border p-4"
      style={{
        background: "var(--accent-bg)",
        borderColor: "var(--accent-border)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 3,
          background: "var(--accent)",
          borderRadius: "3px 0 0 3px",
        }}
      />
      <div className="mb-2 flex items-center gap-2">
        <span className="text-lg">&#x1F451;</span>
        <span
          className="text-[10px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--accent)" }}
        >
          Captain
        </span>
      </div>
      <div className="mb-1 text-lg font-bold text-zinc-100">
        {captain.name}
      </div>
      {captain.rationale && (
        <p className="mb-2 text-[13px] leading-relaxed text-zinc-400">
          &ldquo;{captain.rationale}&rdquo;
        </p>
      )}
      <ConvictionMeter level={captain.conviction} />
    </div>
  );
}

/* ── Trade history ─────────────────────────────────────────────── */

function TradeHistory({ trades }: { trades: TradeEntry[] }) {
  if (trades.length === 0) {
    return (
      <p className="text-[13px] text-zinc-600">
        No trades yet. Watching the market.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {trades.map((t, i) => (
        <div
          key={i}
          className="rounded-xl border px-3.5 py-2.5"
          style={{ borderColor: "var(--border)", background: "rgba(255, 255, 255, 0.02)" }}
        >
          <div className="flex items-center gap-2 text-[12px]">
            <span className="font-mono text-[10px] text-zinc-600">
              Rd {t.round}
            </span>
            <span style={{ color: "rgb(239, 68, 68)" }}>{t.player_out}</span>
            <span className="text-zinc-600">&rarr;</span>
            <span style={{ color: "rgb(80, 200, 120)" }}>{t.player_in}</span>
          </div>
          {t.rationale && (
            <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">
              &ldquo;{t.rationale}&rdquo;
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Plan card ─────────────────────────────────────────────────── */

function PlanCard({ plan }: { plan: SquadPlan }) {
  return (
    <div
      className="rounded-xl border p-4"
      style={{
        background: "rgba(255, 255, 255, 0.02)",
        borderColor: "var(--border)",
      }}
    >
      <p className="text-[13px] leading-relaxed text-zinc-400">
        &ldquo;{plan.text}&rdquo;
      </p>
      {plan.round && (
        <span className="mt-2 inline-block font-mono text-[10px] text-zinc-600">
          Round {plan.round}
        </span>
      )}
    </div>
  );
}

/* ── Section header ────────────────────────────────────────────── */

function SectionHeader({
  icon,
  title,
  detail,
}: {
  icon: string;
  title: string;
  detail?: string;
}) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <div
        className="flex h-7 w-7 items-center justify-center rounded-lg text-sm"
        style={{
          background: "var(--accent-bg)",
          border: "1px solid var(--accent-border)",
        }}
      >
        {icon}
      </div>
      <h2 className="text-sm font-semibold text-zinc-200">{title}</h2>
      {detail && (
        <span className="ml-auto font-mono text-[10px] text-zinc-600">
          {detail}
        </span>
      )}
    </div>
  );
}

/* ── Empty state ───────────────────────────────────────────────── */

function EmptySquad() {
  return (
    <div className="mx-auto max-w-[720px] px-6 py-10">
      <h1 className="mb-4 text-2xl font-bold text-zinc-200">My Squad</h1>
      <div
        className="rounded-xl border p-8 text-center"
        style={{ borderColor: "var(--border)", background: "rgba(255, 255, 255, 0.02)" }}
      >
        <p className="text-[15px] text-zinc-400">
          Squad hasn&apos;t been locked in yet.
        </p>
        <p className="mt-2 text-[13px] text-zinc-600">
          I&apos;m still reading the market. Check back soon.
        </p>
      </div>
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────────────── */

export default function SquadClient({
  data,
}: {
  data: SquadResponse | null;
}) {
  const [selectedSlot, setSelectedSlot] = useState<SquadSlot | null>(null);

  if (!data || data.roster.length === 0) {
    return <EmptySquad />;
  }

  const starting = data.roster.filter((s) => !s.is_bench && s.position !== "FLX");
  const bench = data.roster.filter((s) => s.is_bench && s.position !== "FLX");
  const flexPlayer = data.roster.find((s) => s.position === "FLX");

  const handleSelect = (slot: SquadSlot) => {
    setSelectedSlot((prev) =>
      prev?.slot_index === slot.slot_index ? null : slot,
    );
  };

  return (
    <div className="mx-auto max-w-[720px] px-6 py-10">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-200">My Squad</h1>
        <p className="mt-1 text-[13px] text-zinc-500">
          Here&apos;s my squad. Here&apos;s the logic. Judge me.
        </p>
        <div className="mt-2 flex items-center gap-3">
          <span className="font-mono text-[10px] text-zinc-600">
            Season {data.season}
          </span>
          {data.current_round > 0 && (
            <span className="font-mono text-[10px] text-zinc-600">
              Round {data.current_round}
            </span>
          )}
        </div>
      </div>

      {/* Captain */}
      {data.captain && (
        <div className="mb-6">
          <CaptainCard captain={data.captain} />
        </div>
      )}

      {/* Field layout */}
      <div className="mb-4">
        <FieldLayout
          starting={starting}
          selectedSlot={selectedSlot}
          onSelect={handleSelect}
        />
      </div>

      {/* Selected player detail */}
      {selectedSlot && (
        <div className="mb-6">
          <PlayerDetail slot={selectedSlot} />
        </div>
      )}

      {/* Bench */}
      {bench.length > 0 && (
        <div className="mb-4">
          <SectionHeader
            icon="&#x1FA91;"
            title="Bench"
            detail={`${bench.length} reserves`}
          />
          <div className="flex flex-col gap-1.5">
            {bench.map((slot) => (
              <BenchCard
                key={slot.slot_index}
                slot={slot}
                onSelect={handleSelect}
                isSelected={selectedSlot?.slot_index === slot.slot_index}
              />
            ))}
          </div>
        </div>
      )}

      {/* 18th Man (FLX) */}
      {flexPlayer && (
        <div className="mb-8">
          <SectionHeader icon="&#x1F4A0;" title="18th Man" detail="FLX" />
          <BenchCard
            slot={flexPlayer}
            onSelect={handleSelect}
            isSelected={selectedSlot?.slot_index === flexPlayer.slot_index}
          />
        </div>
      )}

      {/* Selected player detail (bench/flex) */}
      {selectedSlot && (selectedSlot.is_bench || selectedSlot.position === "FLX") && (
        <div className="mb-6">
          <PlayerDetail slot={selectedSlot} />
        </div>
      )}

      {/* Recent Trades */}
      <div className="mb-8">
        <SectionHeader icon="&#x1F504;" title="Recent Trades" />
        <TradeHistory trades={data.recent_trades} />
      </div>

      {/* The Plan */}
      {data.plan && (
        <div className="mb-8">
          <SectionHeader icon="&#x1F52E;" title="The Plan" />
          <PlanCard plan={data.plan} />
        </div>
      )}
    </div>
  );
}
