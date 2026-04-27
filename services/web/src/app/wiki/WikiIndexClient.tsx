"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  Clock,
  FileText,
  Users,
  Radio,
  Calendar,
  ChevronDown,
  Mic,
  Rss,
} from "lucide-react";
import type {
  WikiPageSummary,
  WikiPageType,
  WikiChangeItem,
} from "./wiki-data";
import "./wiki.css";

/* ── Constants ── */

const ITEMS_PER_PAGE = 30;

const TYPE_CONFIG: Record<
  WikiPageType,
  { label: string; icon: typeof FileText }
> = {
  player: { label: "Players", icon: FileText },
  team: { label: "Teams", icon: Users },
  advisor: { label: "Advisors", icon: Mic },
  channel: { label: "Channels", icon: Rss },
  round: { label: "Rounds", icon: Calendar },
};

// Voices is a virtual tab that combines advisor + channel pages.
const VOICES_TYPES: WikiPageType[] = ["advisor", "channel"];

const FILTER_TABS: { key: string; label: string }[] = [
  { key: "all", label: "All" },
  { key: "player", label: "Players" },
  { key: "team", label: "Teams" },
  { key: "voices", label: "Voices" },
  { key: "round", label: "Rounds" },
];

/* ── Helpers ── */

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  return new Date(iso).toLocaleDateString("en-AU", {
    day: "numeric",
    month: "short",
  });
}

function pageHref(page: { page_type: WikiPageType; slug: string }): string {
  if (page.page_type === "round") {
    const match = page.slug.match(/^round-(\d+)-(\d+)$/);
    if (match) return `/wiki/round/${match[1]}/${match[2]}`;
  }
  return `/wiki/${page.page_type}/${page.slug}`;
}

function changeHref(c: WikiChangeItem): string {
  return pageHref({ page_type: c.page_type, slug: c.page_slug });
}

/** Extract team name from metadata_json, or null */
function getTeam(page: WikiPageSummary): string | null {
  return (page.metadata_json?.team as string) ?? null;
}

/* ── Style tokens (CSS var refs) ── */

const v = {
  surface: "var(--wiki-surface)",
  bg: "var(--wiki-bg)",
  border: "var(--wiki-border)",
  ink: "var(--wiki-ink)",
  inkMuted: "var(--wiki-ink-muted)",
  inkFaint: "var(--wiki-ink-faint)",
  accent: "var(--wiki-accent)",
  accentBg: "var(--wiki-accent-bg)",
  amberBg: "var(--wiki-amber-bg)",
  amber: "var(--wiki-amber)",
  greenBg: "var(--wiki-green-bg)",
  green: "var(--wiki-green)",
  tealBg: "var(--wiki-teal-bg)",
  teal: "var(--wiki-teal)",
  purpleBg: "var(--wiki-purple-bg)",
  purple: "var(--wiki-purple)",
  serif: "var(--font-serif), Georgia, serif",
};

/* ══════════════════════════════════════════════════════
   Main component
   ══════════════════════════════════════════════════════ */

interface WikiIndexClientProps {
  pages: WikiPageSummary[];
  recentChanges?: WikiChangeItem[];
}

export default function WikiIndexClient({
  pages,
  recentChanges = [],
}: WikiIndexClientProps) {
  const [activeFilter, setActiveFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    let result = pages;
    if (activeFilter === "voices") {
      result = result.filter((p) => VOICES_TYPES.includes(p.page_type));
    } else if (activeFilter !== "all") {
      result = result.filter((p) => p.page_type === activeFilter);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          (getTeam(p) ?? "").toLowerCase().includes(q),
      );
    }
    return result;
  }, [pages, activeFilter, search]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {
      player: 0,
      team: 0,
      advisor: 0,
      channel: 0,
      round: 0,
      voices: 0,
    };
    for (const p of pages) {
      c[p.page_type] = (c[p.page_type] || 0) + 1;
      if (VOICES_TYPES.includes(p.page_type)) c.voices += 1;
    }
    return c;
  }, [pages]);

  const isDashboard = activeFilter === "all" && !search;

  return (
    <div className="min-h-screen">
      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* Editorial header */}
        <header
          style={{
            maxWidth: 640,
            margin: "0 auto 3rem",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: v.accent,
              marginBottom: "0.85rem",
            }}
          >
            The Wiki
          </div>
          <h1
            style={{
              fontFamily: v.serif,
              fontSize: "clamp(2.2rem, 5vw, 3rem)",
              fontWeight: 700,
              color: v.ink,
              lineHeight: 1.1,
              marginBottom: "0.6rem",
            }}
          >
            Knowledge Base
          </h1>
          <p
            style={{
              fontFamily: v.serif,
              fontSize: "1.05rem",
              fontStyle: "italic",
              color: v.inkMuted,
              lineHeight: 1.5,
            }}
          >
            Players, teams, voices and rounds — written and maintained by
            Jaromelu.
          </p>
        </header>

        {/* Sub-bar (filter + search) only on filtered/search views */}
        {!isDashboard && (
          <div
            className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-8"
            style={{
              paddingBottom: "1rem",
              borderBottom: `1px solid ${v.border}`,
            }}
          >
            <div className="flex flex-wrap gap-1">
              {FILTER_TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveFilter(tab.key)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-md transition-colors"
                  style={{
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    backgroundColor:
                      activeFilter === tab.key ? v.accentBg : "transparent",
                    color: activeFilter === tab.key ? v.accent : v.inkFaint,
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <input
              type="text"
              placeholder="Search pages..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full sm:w-64 sm:ml-auto px-3 py-2 text-sm rounded-lg border focus:outline-none"
              style={{
                borderColor: v.border,
                background: v.surface,
                color: v.ink,
              }}
            />
          </div>
        )}

        {/* ── Tab content ── */}
        {isDashboard ? (
          <Dashboard
            counts={counts}
            recentChanges={recentChanges}
            onNavigate={setActiveFilter}
            search={search}
            onSearch={setSearch}
          />
        ) : activeFilter === "player" ? (
          <PlayersTab pages={filtered} search={search} />
        ) : activeFilter === "all" && search ? (
          <SearchResults pages={filtered} />
        ) : (
          <PaginatedGrid pages={filtered} />
        )}

        {filtered.length === 0 && activeFilter !== "all" && (
          <div
            style={{
              textAlign: "center",
              padding: "4rem 0",
              color: v.inkFaint,
            }}
          >
            <FileText
              size={32}
              style={{ marginBottom: "0.75rem", opacity: 0.5 }}
            />
            <p style={{ fontSize: "14px" }}>No pages found.</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Dashboard — Explore topics + Recently Updated +
   How this connects (static teaser) + footer
   ══════════════════════════════════════════════════════ */

const NEW_BADGE_HOURS = 72;

function isNew(iso: string): boolean {
  const hours = (Date.now() - new Date(iso).getTime()) / 3600000;
  return hours < NEW_BADGE_HOURS;
}

function Dashboard({
  counts,
  recentChanges,
  onNavigate,
  search,
  onSearch,
}: {
  counts: Record<string, number>;
  recentChanges: WikiChangeItem[];
  onNavigate: (tab: string) => void;
  search: string;
  onSearch: (s: string) => void;
}) {
  // Dashboard tiles use a "voices" virtual tile that combines advisor + channel.
  type TopicKey = "player" | "team" | "voices" | "round";
  const topicOrder: TopicKey[] = ["player", "team", "voices", "round"];
  const topicConfig: Record<
    TopicKey,
    { label: string; icon: typeof FileText; copy: string }
  > = {
    player: {
      label: "Players",
      icon: FileText,
      copy: "Profiles, form, value calls.",
    },
    team: {
      label: "Teams",
      icon: Users,
      copy: "Squads, structures, edges.",
    },
    voices: {
      label: "Voices",
      icon: Radio,
      copy: "Channels and the people behind them.",
    },
    round: {
      label: "Rounds",
      icon: Calendar,
      copy: "Matchups, recaps, predictions.",
    },
  };

  return (
    <>
      {/* ── Section: Explore topics ── */}
      <section style={{ paddingBottom: "3rem" }}>
        <SectionLabel>Explore topics</SectionLabel>
        <SectionTitle>Pick a place to start.</SectionTitle>
        <SectionSubtitle>
          Four directions through the knowledge base. Tap any to dive in.
        </SectionSubtitle>

        <div
          style={{
            display: "grid",
            gap: "1px",
            background: v.border,
            border: `1px solid ${v.border}`,
            marginTop: "1.5rem",
          }}
          className="grid-cols-2 md:grid-cols-4"
        >
          {topicOrder.map((key) => {
            const cfg = topicConfig[key];
            const Icon = cfg.icon;
            return (
              <button
                key={key}
                onClick={() => onNavigate(key)}
                style={{
                  background: v.surface,
                  padding: "1.6rem 1.2rem",
                  textAlign: "left",
                  cursor: "pointer",
                  border: "none",
                  fontFamily: "inherit",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = v.bg;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = v.surface;
                }}
              >
                <Icon
                  size={18}
                  style={{ color: v.accent, marginBottom: "0.6rem" }}
                />
                <div
                  style={{
                    fontFamily: v.serif,
                    fontSize: "1.4rem",
                    fontWeight: 700,
                    color: v.ink,
                    lineHeight: 1.1,
                  }}
                >
                  {cfg.label}
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: v.inkMuted,
                    marginTop: "0.25rem",
                    lineHeight: 1.4,
                  }}
                >
                  {cfg.copy}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: v.inkFaint,
                    marginTop: "0.85rem",
                  }}
                >
                  {counts[key] ?? 0}{" "}
                  {(counts[key] ?? 0) === 1
                    ? cfg.label.slice(0, -1)
                    : cfg.label}
                </div>
              </button>
            );
          })}
        </div>

        {/* Inline search — secondary affordance, after the tabs */}
        <div style={{ marginTop: "1.5rem", maxWidth: 360 }}>
          <input
            type="text"
            placeholder="Or search pages..."
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg border focus:outline-none"
            style={{
              borderColor: v.border,
              background: v.surface,
              color: v.ink,
            }}
          />
        </div>
      </section>

      {/* ── Section: Recently Updated ── */}
      {recentChanges.length > 0 && (
        <section
          style={{
            paddingTop: "2.5rem",
            paddingBottom: "3rem",
            borderTop: `1px solid ${v.border}`,
          }}
        >
          <SectionLabel>Recently Updated</SectionLabel>
          <SectionTitle>What Jaromelu touched lately.</SectionTitle>
          <SectionSubtitle>
            Live revisions across the wiki, freshest first.
          </SectionSubtitle>

          <RecentList items={recentChanges} />
        </section>
      )}

      {/* ── Section: How this connects (static teaser) ── */}
      <section
        style={{
          paddingTop: "2.5rem",
          paddingBottom: "3rem",
          borderTop: `1px solid ${v.border}`,
        }}
      >
        <SectionLabel>How this connects</SectionLabel>
        <SectionTitle>The map of NRL knowledge.</SectionTitle>
        <SectionSubtitle>
          Soon: hover to explore the relations between players, teams, rounds
          and the voices talking about them.
        </SectionSubtitle>

        <ConnectsTeaser />
      </section>

      {/* ── Footer ── */}
      <footer
        style={{
          marginTop: "1rem",
          paddingTop: "2rem",
          borderTop: `1px solid ${v.border}`,
          textAlign: "center",
          fontSize: "12px",
          color: v.inkFaint,
          letterSpacing: "0.04em",
        }}
      >
        Updated continuously by{" "}
        <Link
          href="/feed"
          style={{
            color: v.accent,
            fontWeight: 500,
            textDecoration: "none",
          }}
        >
          Scout
        </Link>
        .
      </footer>
    </>
  );
}

/* ── Recently Updated list ── */

function RecentList({ items }: { items: WikiChangeItem[] }) {
  return (
    <ol
      style={{
        listStyle: "none",
        padding: 0,
        margin: "1.5rem 0 0",
        background: v.surface,
        border: `1px solid ${v.border}`,
      }}
    >
      {items.slice(0, 6).map((c, i) => (
        <li
          key={c.revision_id}
          style={{
            borderTop: i === 0 ? "none" : `1px solid ${v.border}`,
          }}
        >
          <Link
            href={changeHref(c)}
            className="group block transition-colors"
            style={{
              padding: "1rem 1.2rem",
              display: "flex",
              alignItems: "center",
              gap: "0.85rem",
              textDecoration: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = v.bg;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            <RecentTypeIcon type={c.page_type} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                className="flex items-center gap-2"
                style={{ marginBottom: "0.15rem" }}
              >
                <span
                  className="group-hover:underline"
                  style={{
                    fontSize: "14px",
                    fontWeight: 600,
                    color: v.ink,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {c.page_title}
                </span>
                {isNew(c.created_at) && <NewBadge />}
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: v.inkFaint,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {c.summary || c.section_heading || "Updated"}
              </div>
            </div>
            <span
              style={{
                fontSize: "11px",
                color: v.inkFaint,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {formatRelative(c.created_at)}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}

function NewBadge() {
  return (
    <span
      style={{
        fontSize: "9px",
        fontWeight: 700,
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        padding: "0.15rem 0.4rem",
        borderRadius: "2px",
        background: v.greenBg,
        color: v.green,
        flexShrink: 0,
      }}
    >
      New
    </span>
  );
}

/* ── How this connects — static teaser ── */

function ConnectsTeaser() {
  return (
    <div
      style={{
        position: "relative",
        marginTop: "1.5rem",
        background: v.surface,
        border: `1px solid ${v.border}`,
        padding: "3rem 1.5rem",
        minHeight: 260,
        overflow: "hidden",
      }}
    >
      <svg
        viewBox="0 0 600 240"
        preserveAspectRatio="xMidYMid meet"
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          opacity: 0.6,
        }}
      >
        <line x1="300" y1="110" x2="108" y2="53" stroke="var(--wiki-border)" strokeWidth="1" />
        <line x1="300" y1="110" x2="492" y2="53" stroke="var(--wiki-border)" strokeWidth="1" />
        <line x1="300" y1="110" x2="108" y2="173" stroke="var(--wiki-border)" strokeWidth="1" />
        <line x1="300" y1="110" x2="492" y2="173" stroke="var(--wiki-border)" strokeWidth="1" />
        <line x1="300" y1="110" x2="300" y2="34" stroke="var(--wiki-border)" strokeWidth="1" />
      </svg>

      <NodeChip x="50%" y="46%" emphasis>Edge Attack</NodeChip>
      <NodeChip x="18%" y="22%">Player</NodeChip>
      <NodeChip x="82%" y="22%">Team</NodeChip>
      <NodeChip x="18%" y="72%">Voice</NodeChip>
      <NodeChip x="82%" y="72%">Round</NodeChip>
      <NodeChip x="50%" y="14%">Tactic</NodeChip>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 14,
          textAlign: "center",
          fontSize: "11px",
          fontWeight: 600,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: v.inkFaint,
        }}
      >
        Graph view coming soon
      </div>
    </div>
  );
}

function NodeChip({
  x,
  y,
  children,
  emphasis,
}: {
  x: string;
  y: string;
  children: React.ReactNode;
  emphasis?: boolean;
}) {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: "translate(-50%, -50%)",
        padding: emphasis ? "0.45rem 0.85rem" : "0.3rem 0.65rem",
        background: emphasis ? v.accentBg : v.bg,
        color: emphasis ? v.accent : v.inkMuted,
        border: emphasis ? `1px solid ${v.accent}` : `1px solid ${v.border}`,
        borderRadius: 999,
        fontSize: emphasis ? "13px" : "11px",
        fontWeight: emphasis ? 600 : 500,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </div>
  );
}

/* ── Editorial section primitives ── */

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: v.accent,
        marginBottom: "0.5rem",
      }}
    >
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2
      style={{
        fontFamily: v.serif,
        fontSize: "clamp(1.5rem, 3vw, 2rem)",
        fontWeight: 700,
        color: v.ink,
        lineHeight: 1.2,
        marginBottom: "0.4rem",
      }}
    >
      {children}
    </h2>
  );
}

function SectionSubtitle({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: v.serif,
        fontStyle: "italic",
        fontSize: "1rem",
        color: v.inkMuted,
        lineHeight: 1.5,
        maxWidth: 540,
      }}
    >
      {children}
    </p>
  );
}

function RecentTypeIcon({ type }: { type: WikiPageType }) {
  const config: Record<
    WikiPageType,
    { bg: string; color: string; letter: string }
  > = {
    player: { bg: v.tealBg, color: v.teal, letter: "P" },
    team: { bg: v.accentBg, color: v.accent, letter: "T" },
    advisor: { bg: v.purpleBg, color: v.purple, letter: "A" },
    channel: { bg: v.purpleBg, color: v.purple, letter: "C" },
    round: { bg: v.amberBg, color: v.amber, letter: "R" },
  };
  const c = config[type];
  return (
    <div
      style={{
        width: 28,
        height: 28,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "12px",
        fontWeight: 600,
        background: c.bg,
        color: c.color,
        flexShrink: 0,
      }}
    >
      {c.letter}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Players Tab — grouped by team or alphabetically,
   collapsible, with A-Z jump bar
   ══════════════════════════════════════════════════════ */

function PlayersTab({
  pages,
  search,
}: {
  pages: WikiPageSummary[];
  search: string;
}) {
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    new Set(),
  );

  const { groups, groupKeys } = useMemo(() => {
    const hasTeams = pages.some((p) => getTeam(p));

    if (hasTeams) {
      const map = new Map<string, WikiPageSummary[]>();
      const noTeam: WikiPageSummary[] = [];
      for (const p of pages) {
        const team = getTeam(p);
        if (team) {
          if (!map.has(team)) map.set(team, []);
          map.get(team)!.push(p);
        } else {
          noTeam.push(p);
        }
      }
      const sorted = [...map.entries()].sort((a, b) =>
        a[0].localeCompare(b[0]),
      );
      if (noTeam.length > 0) sorted.push(["Other", noTeam]);
      const groups = new Map(sorted);
      return { groups, groupKeys: [...groups.keys()] };
    } else {
      const map = new Map<string, WikiPageSummary[]>();
      for (const p of pages) {
        const letter = p.title[0]?.toUpperCase() || "#";
        if (!map.has(letter)) map.set(letter, []);
        map.get(letter)!.push(p);
      }
      const sorted = new Map(
        [...map.entries()].sort((a, b) => a[0].localeCompare(b[0])),
      );
      return { groups: sorted, groupKeys: [...sorted.keys()] };
    }
  }, [pages]);

  const toggleGroup = (key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const collapseAll = () => setCollapsedGroups(new Set(groupKeys));
  const expandAll = () => setCollapsedGroups(new Set());

  const activeLetters = useMemo(() => {
    return new Set(groupKeys.map((k) => k[0]?.toUpperCase()));
  }, [groupKeys]);

  return (
    <>
      {/* Controls row */}
      <div className="flex items-center justify-between mb-3">
        <SectionHeading icon={FileText} label="Players" count={pages.length} />
        {groupKeys.length > 3 && (
          <div className="flex gap-2">
            <button
              onClick={expandAll}
              style={{
                fontSize: "11px",
                color: v.accent,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              Expand all
            </button>
            <button
              onClick={collapseAll}
              style={{
                fontSize: "11px",
                color: v.inkFaint,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              Collapse all
            </button>
          </div>
        )}
      </div>

      {/* A-Z bar */}
      {!search && groupKeys.length > 5 && (
        <div className="flex flex-wrap gap-0.5 mb-4">
          {"ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((letter) => {
            const active = activeLetters.has(letter);
            return (
              <button
                key={letter}
                disabled={!active}
                onClick={() => {
                  const target = groupKeys.find(
                    (k) => k[0]?.toUpperCase() === letter,
                  );
                  if (target) {
                    document
                      .getElementById(`group-${target}`)
                      ?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }
                }}
                style={{
                  width: 28,
                  height: 28,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "11px",
                  fontWeight: 600,
                  color: active ? v.inkMuted : v.inkFaint,
                  borderRadius: "4px",
                  border: "none",
                  background: "none",
                  cursor: active ? "pointer" : "default",
                  opacity: active ? 1 : 0.3,
                }}
                onMouseEnter={(e) => {
                  if (active) {
                    e.currentTarget.style.background = v.accentBg;
                    e.currentTarget.style.color = v.accent;
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "none";
                  e.currentTarget.style.color = active
                    ? v.inkMuted
                    : v.inkFaint;
                }}
              >
                {letter}
              </button>
            );
          })}
        </div>
      )}

      {/* Groups */}
      {groupKeys.map((key) => {
        const groupPages = groups.get(key) || [];
        const isCollapsed = collapsedGroups.has(key);

        return (
          <div key={key} id={`group-${key}`} style={{ marginBottom: "1.5rem" }}>
            <button
              onClick={() => toggleGroup(key)}
              className="flex items-center gap-2 w-full text-left"
              style={{
                padding: "0.6rem 0",
                cursor: "pointer",
                background: "none",
                border: "none",
                borderBottom: `1px solid ${v.border}`,
                marginBottom: isCollapsed ? 0 : "0.5rem",
                fontFamily: "inherit",
              }}
            >
              <ChevronDown
                size={14}
                style={{
                  color: v.inkFaint,
                  transition: "transform 0.2s",
                  transform: isCollapsed ? "rotate(-90deg)" : "rotate(0)",
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontFamily: v.serif,
                  fontSize: "1rem",
                  fontWeight: 700,
                  color: v.ink,
                }}
              >
                {key}
              </span>
              <span
                style={{
                  fontSize: "12px",
                  color: v.inkFaint,
                  marginLeft: "auto",
                }}
              >
                {groupPages.length}{" "}
                {groupPages.length === 1 ? "player" : "players"}
              </span>
            </button>

            {!isCollapsed && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: "1px",
                  background: v.border,
                  border: `1px solid ${v.border}`,
                }}
              >
                {groupPages.map((page) => (
                  <Link
                    key={page.page_id}
                    href={pageHref(page)}
                    className="group block transition-colors"
                    style={{ background: v.surface, padding: "0.8rem 1rem" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = v.bg;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = v.surface;
                    }}
                  >
                    <div className="flex items-center gap-2">
                      {typeof page.metadata_json?.position === "string" && (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 600,
                            letterSpacing: "0.06em",
                            padding: "0.1rem 0.35rem",
                            borderRadius: "2px",
                            background: v.amberBg,
                            color: v.amber,
                            flexShrink: 0,
                          }}
                        >
                          {page.metadata_json.position}
                        </span>
                      )}
                      <span
                        className="group-hover:underline"
                        style={{
                          fontSize: "14px",
                          fontWeight: 500,
                          color: v.ink,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {page.title}
                      </span>
                      {page.status !== "published" && (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 600,
                            letterSpacing: "0.08em",
                            textTransform: "uppercase",
                            padding: "0.1rem 0.35rem",
                            borderRadius: "2px",
                            background: v.amberBg,
                            color: v.amber,
                            flexShrink: 0,
                          }}
                        >
                          {page.status}
                        </span>
                      )}
                      {page.metadata_json?.price != null && (
                        <span
                          style={{
                            fontSize: "12px",
                            color: v.inkFaint,
                            marginLeft: "auto",
                            flexShrink: 0,
                          }}
                        >
                          $
                          {(
                            page.metadata_json.price as number
                          ).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

/* ══════════════════════════════════════════════════════
   Search Results — grouped by type when searching "all"
   ══════════════════════════════════════════════════════ */

function SearchResults({ pages }: { pages: WikiPageSummary[] }) {
  const grouped = useMemo(() => {
    const groups: Partial<Record<WikiPageType, WikiPageSummary[]>> = {};
    for (const page of pages) {
      if (!groups[page.page_type]) groups[page.page_type] = [];
      groups[page.page_type]!.push(page);
    }
    return groups;
  }, [pages]);

  if (pages.length === 0) {
    return (
      <div
        style={{
          textAlign: "center",
          padding: "4rem 0",
          color: v.inkFaint,
        }}
      >
        <FileText
          size={32}
          style={{ marginBottom: "0.75rem", opacity: 0.5 }}
        />
        <p style={{ fontSize: "14px" }}>No pages found.</p>
      </div>
    );
  }

  return (
    <>
      {Object.entries(grouped).map(([type, groupPages]) => {
        const config = TYPE_CONFIG[type as WikiPageType];
        const Icon = config?.icon || FileText;
        return (
          <div key={type} className="mb-8">
            <SectionHeading
              icon={Icon}
              label={config?.label || type}
              count={groupPages!.length}
            />
            <PageGrid pages={groupPages!} />
          </div>
        );
      })}
    </>
  );
}

/* ══════════════════════════════════════════════════════
   Paginated Grid — for teams, advisors, rounds
   ══════════════════════════════════════════════════════ */

function PaginatedGrid({ pages }: { pages: WikiPageSummary[] }) {
  const [currentPage, setCurrentPage] = useState(0);

  const totalPageCount = Math.ceil(pages.length / ITEMS_PER_PAGE);
  const needsPagination = totalPageCount > 1;
  const visiblePages = needsPagination
    ? pages.slice(
        currentPage * ITEMS_PER_PAGE,
        (currentPage + 1) * ITEMS_PER_PAGE,
      )
    : pages;

  return (
    <>
      <PageGrid pages={visiblePages} />

      {needsPagination && (
        <div
          className="flex items-center justify-center gap-1"
          style={{ padding: "1.5rem 0" }}
        >
          <PaginationBtn
            disabled={currentPage === 0}
            onClick={() => setCurrentPage((p) => p - 1)}
          >
            &laquo;
          </PaginationBtn>
          {Array.from({ length: totalPageCount }, (_, i) => {
            if (
              i === 0 ||
              i === totalPageCount - 1 ||
              Math.abs(i - currentPage) <= 1
            ) {
              return (
                <PaginationBtn
                  key={i}
                  active={i === currentPage}
                  onClick={() => setCurrentPage(i)}
                >
                  {i + 1}
                </PaginationBtn>
              );
            }
            if (i === currentPage - 2 || i === currentPage + 2) {
              return (
                <span
                  key={i}
                  style={{
                    width: 32,
                    textAlign: "center",
                    fontSize: "13px",
                    color: v.inkFaint,
                  }}
                >
                  &hellip;
                </span>
              );
            }
            return null;
          })}
          <PaginationBtn
            disabled={currentPage === totalPageCount - 1}
            onClick={() => setCurrentPage((p) => p + 1)}
          >
            &raquo;
          </PaginationBtn>
        </div>
      )}
    </>
  );
}

function PaginationBtn({
  children,
  active,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        width: 32,
        height: 32,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "13px",
        fontWeight: 500,
        borderRadius: "6px",
        border: `1px solid ${active ? v.accent : v.border}`,
        background: active ? v.accent : v.surface,
        color: active ? "white" : v.inkMuted,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.3 : 1,
        fontFamily: "inherit",
      }}
    >
      {children}
    </button>
  );
}

/* ══════════════════════════════════════════════════════
   Shared components
   ══════════════════════════════════════════════════════ */

function SectionHeading({
  icon: Icon,
  label,
  count,
}: {
  icon: typeof FileText;
  label: string;
  count: number;
}) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={16} style={{ color: v.accent }} />
      <h2
        style={{
          fontSize: "11px",
          fontWeight: 600,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: v.inkFaint,
        }}
      >
        {label}
      </h2>
      <span style={{ fontSize: "12px", color: v.inkFaint }}>({count})</span>
    </div>
  );
}

function PageGrid({ pages }: { pages: WikiPageSummary[] }) {
  return (
    <div
      style={{
        display: "grid",
        gap: "1px",
        background: v.border,
        border: `1px solid ${v.border}`,
      }}
      className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
    >
      {pages.map((page) => (
        <Link
          key={page.page_id}
          href={pageHref(page)}
          className="group block transition-colors"
          style={{ background: v.surface, padding: "1.4rem" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = v.bg;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = v.surface;
          }}
        >
          <h3
            className="group-hover:underline"
            style={{
              fontFamily: v.serif,
              fontSize: "1.1rem",
              fontWeight: 700,
              color: v.ink,
              marginBottom: "0.3rem",
            }}
          >
            {page.title}
          </h3>
          {page.summary && (
            <p
              className="line-clamp-2"
              style={{
                fontSize: "13px",
                color: v.inkMuted,
                marginBottom: "0.5rem",
                lineHeight: 1.5,
              }}
            >
              {page.summary}
            </p>
          )}
          <div
            className="flex items-center gap-2"
            style={{ fontSize: "11px", color: v.inkFaint }}
          >
            <Clock size={10} />
            <span>{formatRelative(page.updated_at)}</span>
            {page.status !== "published" && (
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 600,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  padding: "0.15rem 0.4rem",
                  borderRadius: "2px",
                  background: v.amberBg,
                  color: v.amber,
                }}
              >
                {page.status}
              </span>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
