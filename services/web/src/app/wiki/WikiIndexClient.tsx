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
  advisor: { label: "Advisors", icon: Radio },
  round: { label: "Rounds", icon: Calendar },
};

const FILTER_TABS: { key: string; label: string }[] = [
  { key: "all", label: "All" },
  { key: "player", label: "Players" },
  { key: "team", label: "Teams" },
  { key: "advisor", label: "Advisors" },
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
    if (activeFilter !== "all")
      result = result.filter((p) => p.page_type === activeFilter);
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
      round: 0,
    };
    for (const p of pages) c[p.page_type] = (c[p.page_type] || 0) + 1;
    return c;
  }, [pages]);

  return (
    <div className="min-h-screen">
      <div className="max-w-5xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="mb-6">
          <h1
            style={{
              fontFamily: v.serif,
              fontSize: "1.8rem",
              fontWeight: 600,
              color: v.ink,
              marginBottom: "0.15rem",
            }}
          >
            Knowledge Base
          </h1>
          <p style={{ fontSize: "14px", color: v.inkFaint }}>
            Players, teams, advisors, rounds.
          </p>
        </div>

        {/* Search + Filters */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-6">
          <input
            type="text"
            placeholder="Search pages..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full sm:w-64 px-3 py-2 text-sm rounded-lg border focus:outline-none"
            style={{
              borderColor: v.border,
              background: v.surface,
              color: v.ink,
            }}
          />
          <div className="flex gap-1">
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
        </div>

        {/* ── Tab content ── */}
        {activeFilter === "all" && !search ? (
          <AllDashboard
            counts={counts}
            totalPages={pages.length}
            recentChanges={recentChanges}
            onNavigate={setActiveFilter}
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
   "All" Dashboard — summary cards + recent changes
   ══════════════════════════════════════════════════════ */

function AllDashboard({
  counts,
  totalPages,
  recentChanges,
  onNavigate,
}: {
  counts: Record<string, number>;
  totalPages: number;
  recentChanges: WikiChangeItem[];
  onNavigate: (tab: string) => void;
}) {
  const cards: { key: WikiPageType; count: number; label: string }[] = [
    { key: "player", count: counts.player, label: "Players" },
    { key: "team", count: counts.team, label: "Teams" },
    { key: "advisor", count: counts.advisor, label: "Advisors" },
    { key: "round", count: counts.round, label: "Rounds" },
  ];

  return (
    <>
      {/* Summary cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "1px",
          background: v.border,
          border: `1px solid ${v.border}`,
          marginBottom: "2rem",
        }}
      >
        {cards.map((c) => {
          const Icon = TYPE_CONFIG[c.key].icon;
          return (
            <button
              key={c.key}
              onClick={() => onNavigate(c.key)}
              className="transition-colors"
              style={{
                background: v.surface,
                padding: "1.8rem 1.4rem",
                textAlign: "center",
                cursor: "pointer",
                border: "none",
                fontFamily: "inherit",
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
                style={{
                  color: v.accent,
                  marginBottom: "0.5rem",
                  display: "inline-block",
                }}
              />
              <div
                style={{
                  fontFamily: v.serif,
                  fontSize: "2.8rem",
                  fontWeight: 600,
                  color: v.ink,
                  lineHeight: 1,
                  marginBottom: "0.4rem",
                }}
              >
                {c.count}
              </div>
              <div
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: v.inkFaint,
                }}
              >
                {c.label}
              </div>
            </button>
          );
        })}
      </div>

      {/* Recent changes */}
      {recentChanges.length > 0 && (
        <div>
          <SectionHeading
            icon={Clock}
            label="Recently Updated"
            count={recentChanges.length}
          />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: "1px",
              background: v.border,
              border: `1px solid ${v.border}`,
            }}
          >
            {recentChanges.map((c) => (
              <Link
                key={c.revision_id}
                href={changeHref(c)}
                className="group block transition-colors"
                style={{ background: v.surface, padding: "1rem 1.2rem" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = v.bg;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = v.surface;
                }}
              >
                <div className="flex items-start gap-3">
                  <RecentTypeIcon type={c.page_type} />
                  <div>
                    <div
                      className="group-hover:underline"
                      style={{
                        fontSize: "14px",
                        fontWeight: 500,
                        color: v.ink,
                        marginBottom: "0.1rem",
                      }}
                    >
                      {c.page_title}
                    </div>
                    <div style={{ fontSize: "12px", color: v.inkFaint }}>
                      {c.summary || c.section_heading || "Updated"} &middot;{" "}
                      {formatRelative(c.created_at)}
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Fallback if no recent changes */}
      {recentChanges.length === 0 && totalPages > 0 && (
        <p
          style={{
            fontSize: "14px",
            color: v.inkFaint,
            textAlign: "center",
            padding: "2rem 0",
          }}
        >
          {totalPages} pages in the knowledge base.
        </p>
      )}
    </>
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
                  fontWeight: 600,
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
              fontWeight: 600,
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
