"use client";

import { useEffect, useState } from "react";
import {
  Search,
  PenLine,
  Brain,
  BarChart3,
  BookOpen,
  Play,
  Radio,
  FileText,
  MessageCircle,
  Sparkles,
  MapPin,
  Clock,
  type LucideIcon,
} from "lucide-react";
import type {
  CrewMember,
  PulseContext,
  PulseIconKey,
  PulsePhase,
  PulseResponse,
  SourceType,
  TimelineEntry,
} from "./pulse-data";

const REFRESH_MS = 30_000;

const ICON_MAP: Record<PulseIconKey, LucideIcon> = {
  search: Search,
  pen: PenLine,
  brain: Brain,
  chart: BarChart3,
  book: BookOpen,
  play: Play,
  radio: Radio,
  doc: FileText,
  chat: MessageCircle,
  spark: Sparkles,
};

const SOURCE_ICON: Record<SourceType, LucideIcon> = {
  video: Play,
  podcast: Radio,
  article: FileText,
  tweet: MessageCircle,
  stats: BarChart3,
  feed: Search,
  schedule: Sparkles,
};

function tLabel(min: number): string {
  if (min === 0) return "now";
  if (min < 0) {
    const m = -min;
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  }
  if (min < 60) return `in ${min}m`;
  return `in ${Math.floor(min / 60)}h`;
}

export default function PulseClient({ initial }: { initial: PulseResponse }) {
  const [data, setData] = useState<PulseResponse>(initial);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch("/api/pulse", { cache: "no-store" });
        if (!res.ok) return;
        const next = (await res.json()) as PulseResponse;
        if (!cancelled) setData(next);
      } catch {
        // network blip — leave existing data alone
      }
    };
    const id = setInterval(tick, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const { context, crew, timeline } = data;
  const running = timeline.filter((e) => e.kind === "running");
  const recent = timeline
    .filter((e) => e.kind === "discovered" || e.kind === "processed")
    .slice(-8)
    .reverse();
  const last4hCount = timeline.filter(
    (e) => e.kind === "discovered" && e.t >= -240
  ).length;

  return (
    <div className="mx-auto max-w-[1240px] px-10 pt-8 pb-20">
      <PageContextStrip context={context} />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-9 items-start">
        <div>
          <PulseStrip running={running} crew={crew} last4hCount={last4hCount} />

          <h1
            className="mt-2 mb-1"
            style={{
              fontFamily: "Georgia, serif",
              fontWeight: 400,
              fontSize: 44,
              color: "var(--wiki-ink-muted)",
              letterSpacing: "-0.01em",
            }}
          >
            Morning, Coach
          </h1>
          <p
            className="m-0 italic"
            style={{ color: "var(--wiki-ink-faint)" }}
          >
            Been busy while you slept. Have a look.
          </p>

          <div className="mt-7 flex flex-col gap-2.5">
            <div
              className="font-mono mb-1"
              style={{
                fontSize: 10,
                letterSpacing: "0.14em",
                color: "var(--wiki-ink-faint)",
              }}
            >
              FRESH FROM THE CREW
            </div>
            {recent.length === 0 ? (
              <p
                className="text-sm italic"
                style={{ color: "var(--wiki-ink-faint)" }}
              >
                Crew is quiet. Check back in a bit.
              </p>
            ) : (
              recent.map((e) => (
                <FeedItemRow key={`${e.t}-${e.agent}-${e.source.title}`} entry={e} crew={crew} />
              ))
            )}
          </div>
        </div>

        <CrewRail crew={crew} timeline={timeline} />
      </div>
    </div>
  );
}

const PHASE_LABEL: Record<PulsePhase, string> = {
  "build-up": "BUILD-UP",
  "game-day": "GAME-DAY",
  review: "REVIEW",
};

function kickoffLabel(min: number): string {
  if (min <= 0) {
    const m = -min;
    if (m < 60) return `Kicked off ${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `Kicked off ${h}h ago`;
    return `Kicked off ${Math.floor(h / 24)}d ago`;
  }
  const d = Math.floor(min / (60 * 24));
  const h = Math.floor((min % (60 * 24)) / 60);
  if (d > 0) {
    return `Kick-off in ${d}d ${String(h).padStart(2, "0")}h`;
  }
  if (h > 0) {
    const mm = min % 60;
    return `Kick-off in ${h}h ${String(mm).padStart(2, "0")}m`;
  }
  return `Kick-off in ${min}m`;
}

function PageContextStrip({ context }: { context: PulseContext }) {
  const { round, phase, fixture } = context;
  const [kickoffMin, setKickoffMin] = useState(fixture.kickoffMinutes);
  const mountedAt = useState(() => Date.now())[0];

  useEffect(() => {
    const tick = () => {
      const elapsedMin = Math.floor((Date.now() - mountedAt) / 60_000);
      setKickoffMin(fixture.kickoffMinutes - elapsedMin);
    };
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [fixture.kickoffMinutes, mountedAt]);

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-5 px-4 py-2.5 rounded-[10px]"
      style={{
        border: "1px solid var(--wiki-border)",
        background: "var(--wiki-surface)",
      }}
    >
      <span
        className="font-mono inline-flex items-center px-2 py-0.5 rounded"
        style={{
          fontSize: 10,
          letterSpacing: "0.16em",
          color: "var(--wiki-accent)",
          background: "var(--wiki-accent-bg)",
          border: "1px solid color-mix(in srgb, var(--wiki-accent) 30%, transparent)",
        }}
      >
        ROUND {round}
      </span>

      <Divider />

      <span
        className="font-mono"
        style={{
          fontSize: 10,
          letterSpacing: "0.18em",
          color: "var(--wiki-ink-muted)",
        }}
      >
        {PHASE_LABEL[phase]}
      </span>

      <Divider />

      <span className="inline-flex items-center gap-2 min-w-0">
        <span style={{ color: "var(--wiki-ink-faint)" }} className="inline-flex shrink-0">
          <MapPin size={12} />
        </span>
        <TeamChip team={fixture.home} />
        <span
          className="font-mono"
          style={{ fontSize: 10, color: "var(--wiki-ink-faint)" }}
        >
          vs
        </span>
        <TeamChip team={fixture.away} />
      </span>

      <div className="flex-1" />

      <span
        className="font-mono shrink-0"
        style={{ fontSize: 11, color: "var(--wiki-ink-muted)" }}
      >
        {fixture.kickoffLabel}
      </span>
      <Divider />
      <span
        className="font-mono shrink-0"
        style={{ fontSize: 11, color: "var(--wiki-ink-muted)" }}
      >
        {fixture.venue}
      </span>
      <Divider />
      <span
        className="font-mono inline-flex items-center gap-1.5 shrink-0"
        style={{
          fontSize: 11,
          color: "var(--wiki-accent)",
        }}
      >
        <Clock size={12} />
        {kickoffLabel(kickoffMin)}
      </span>
    </div>
  );
}

function TeamChip({ team }: { team: { code: string; name: string; color: string } }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Dot color={team.color} size={7} />
      <span
        className="font-mono"
        style={{
          fontSize: 11,
          letterSpacing: "0.06em",
          color: "var(--wiki-ink)",
        }}
      >
        {team.name}
      </span>
    </span>
  );
}

function Divider() {
  return (
    <span
      className="w-px h-3.5 shrink-0"
      style={{ background: "var(--wiki-border)" }}
    />
  );
}

function PulseStrip({
  running,
  crew,
  last4hCount,
}: {
  running: TimelineEntry[];
  crew: CrewMember[];
  last4hCount: number;
}) {
  return (
    <div
      className="flex items-center gap-3.5 mb-7 px-4 py-3 rounded-[10px]"
      style={{
        background:
          "linear-gradient(90deg, var(--wiki-accent-bg), transparent 70%)",
        border: "1px solid color-mix(in srgb, var(--wiki-accent) 22%, transparent)",
      }}
    >
      <span className="inline-flex items-center gap-1.5">
        <Dot color="var(--wiki-accent)" />
        <span
          className="font-mono"
          style={{
            fontSize: 10,
            letterSpacing: "0.18em",
            color: "var(--wiki-accent)",
          }}
        >
          JAROMELU IS WORKING
        </span>
      </span>

      <div className="w-px h-3.5" style={{ background: "var(--wiki-border)" }} />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 min-w-0">
        {running.map((r, i) => {
          const a = crew.find((c) => c.id === r.agent);
          if (!a) return null;
          const ICN = ICON_MAP[a.icon];
          return (
            <span key={i} className="inline-flex items-center gap-2 min-w-0">
              <span style={{ color: a.color }} className="inline-flex shrink-0">
                <ICN size={12} />
              </span>
              <span
                className="font-mono shrink-0"
                style={{
                  color: a.color,
                  fontSize: 10,
                  letterSpacing: "0.1em",
                }}
              >
                {a.name.toUpperCase()}
              </span>
              <span
                className="italic truncate"
                style={{
                  color: "var(--wiki-ink-faint)",
                  fontSize: 12,
                  fontFamily: "Georgia, serif",
                }}
              >
                {r.note}
              </span>
            </span>
          );
        })}
      </div>

      <div className="flex-1" />
      <span
        className="font-mono shrink-0"
        style={{ fontSize: 10, color: "var(--wiki-ink-faint)" }}
      >
        {last4hCount} new in last 4h
      </span>
    </div>
  );
}

function FeedItemRow({
  entry,
  crew,
}: {
  entry: TimelineEntry;
  crew: CrewMember[];
}) {
  const a = crew.find((c) => c.id === entry.agent);
  const ICN = SOURCE_ICON[entry.source.type] ?? FileText;
  const accent = a?.color ?? "var(--wiki-ink-faint)";

  return (
    <div
      className="rounded-[10px] px-3.5 py-3 flex gap-3 items-start"
      style={{
        border: "1px solid var(--wiki-border)",
        background: "var(--wiki-surface)",
      }}
    >
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
        style={{
          background: `color-mix(in srgb, ${accent} 11%, transparent)`,
          border: `1px solid color-mix(in srgb, ${accent} 33%, transparent)`,
          color: accent,
        }}
      >
        <ICN size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span
            className="font-mono"
            style={{
              fontSize: 9,
              letterSpacing: "0.14em",
              color: accent,
            }}
          >
            {(a?.name ?? entry.agent).toUpperCase()} ·{" "}
            {entry.kind === "discovered" ? "FOUND" : "PROCESSED"}
          </span>
          <span
            className="font-mono"
            style={{ color: "var(--wiki-ink-faint)", fontSize: 10 }}
          >
            {tLabel(entry.t)}
          </span>
        </div>
        <div
          className="mt-1"
          style={{ color: "var(--wiki-ink)", fontSize: 14, lineHeight: 1.4 }}
        >
          {entry.source.title}
        </div>
        <div
          className="mt-1 italic"
          style={{
            color: "var(--wiki-ink-muted)",
            fontSize: 12,
            fontFamily: "Georgia, serif",
            lineHeight: 1.4,
          }}
        >
          &ldquo;{entry.note}&rdquo;
        </div>
        {entry.claims && entry.claims.length > 0 && (
          <div className="mt-2 flex flex-col gap-1">
            {entry.claims.slice(0, 2).map((c, i) => (
              <div
                key={i}
                className="pl-2"
                style={{
                  color: "var(--wiki-ink-faint)",
                  fontSize: 11,
                  borderLeft: `2px solid color-mix(in srgb, ${accent} 40%, transparent)`,
                }}
              >
                {c}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CrewRail({
  crew,
  timeline,
}: {
  crew: CrewMember[];
  timeline: TimelineEntry[];
}) {
  return (
    <aside className="hidden lg:flex sticky top-20 flex-col gap-3.5">
      <div
        className="rounded-xl p-3.5"
        style={{
          border: "1px solid var(--wiki-border)",
          background: "var(--wiki-surface)",
        }}
      >
        <div
          className="font-mono mb-3"
          style={{
            fontSize: 10,
            letterSpacing: "0.14em",
            color: "var(--wiki-ink-faint)",
          }}
        >
          THE CREW
        </div>
        <div className="flex flex-col gap-2.5">
          {crew.map((c) => {
            const live = timeline.find(
              (e) => e.kind === "running" && e.agent === c.id
            );
            const queued = timeline.find(
              (e) => e.kind === "queued" && e.agent === c.id
            );
            const recent = [...timeline]
              .reverse()
              .find(
                (e) =>
                  e.agent === c.id &&
                  (e.kind === "discovered" || e.kind === "processed")
              );
            const ICN = ICON_MAP[c.icon];
            const status = live ? "active" : queued ? "queued" : "dormant";
            return (
              <div key={c.id} className="flex items-start gap-2.5">
                <div
                  className="relative w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                  style={{
                    background:
                      status === "active"
                        ? `color-mix(in srgb, ${c.color} 12%, transparent)`
                        : "color-mix(in srgb, var(--wiki-ink) 6%, transparent)",
                    border:
                      status === "active"
                        ? `1px solid ${c.color}`
                        : "1px solid var(--wiki-border)",
                    color:
                      status === "active" ? c.color : "var(--wiki-ink-faint)",
                    boxShadow:
                      status === "active"
                        ? `0 0 12px color-mix(in srgb, ${c.color} 33%, transparent)`
                        : "none",
                    opacity: status === "dormant" ? 0.55 : 1,
                  }}
                >
                  <ICN size={12} />
                  {status === "active" && (
                    <span className="absolute -top-0.5 -right-0.5">
                      <Dot color={c.color} size={6} />
                    </span>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <span
                      className="font-mono"
                      style={{
                        fontSize: 10,
                        letterSpacing: "0.1em",
                        color:
                          status === "active"
                            ? c.color
                            : "var(--wiki-ink-muted)",
                      }}
                    >
                      {c.name.toUpperCase()}
                    </span>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: 9,
                        color: "var(--wiki-ink-faint)",
                      }}
                    >
                      {status === "active"
                        ? "now"
                        : status === "queued" && queued
                        ? tLabel(queued.t)
                        : recent
                        ? tLabel(recent.t)
                        : "—"}
                    </span>
                  </div>
                  <div
                    className="mt-0.5 italic"
                    style={{
                      color: "var(--wiki-ink-faint)",
                      fontSize: 11,
                      fontFamily: "Georgia, serif",
                    }}
                  >
                    {live
                      ? `"${live.note}"`
                      : queued
                      ? `queued · ${queued.note}`
                      : recent
                      ? recent.note
                      : c.role}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div
        className="rounded-[10px] px-3 py-2.5 font-mono"
        style={{
          border: "1px dashed var(--wiki-border)",
          color: "var(--wiki-ink-faint)",
          fontSize: 10,
          letterSpacing: "0.08em",
          lineHeight: 1.5,
        }}
      >
        Next full sweep
        <br />
        <span style={{ color: "var(--wiki-ink-muted)" }}>
          Sat 12:00 — round 7 team-list scan
        </span>
      </div>
    </aside>
  );
}

function Dot({ color, size = 5 }: { color: string; size?: number }) {
  return (
    <span
      className="inline-block rounded-full shrink-0"
      style={{ width: size, height: size, background: color }}
    />
  );
}
