"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Clock, FileText, Users, Radio, Calendar } from "lucide-react";
import type { WikiPageSummary, WikiPageType } from "./wiki-data";
import "./wiki.css";

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-AU", { day: "numeric", month: "short" });
}

function pageHref(page: { page_type: WikiPageType; slug: string }): string {
  if (page.page_type === "round") {
    const match = page.slug.match(/^round-(\d+)-(\d+)$/);
    if (match) return `/wiki/round/${match[1]}/${match[2]}`;
  }
  return `/wiki/${page.page_type}/${page.slug}`;
}

const TYPE_CONFIG: Record<WikiPageType, { label: string; icon: typeof FileText }> = {
  player: { label: "Players", icon: FileText },
  team: { label: "Teams", icon: Users },
  advisor: { label: "Advisors", icon: Radio },
  round: { label: "Rounds", icon: Calendar },
};

const FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "player", label: "Players" },
  { key: "team", label: "Teams" },
  { key: "advisor", label: "Advisors" },
  { key: "round", label: "Rounds" },
];

interface WikiIndexClientProps {
  pages: WikiPageSummary[];
}

export default function WikiIndexClient({ pages }: WikiIndexClientProps) {
  const [activeFilter, setActiveFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    let result = pages;
    if (activeFilter !== "all") result = result.filter((p) => p.page_type === activeFilter);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((p) => p.title.toLowerCase().includes(q));
    }
    return result;
  }, [pages, activeFilter, search]);

  const grouped = useMemo(() => {
    if (activeFilter !== "all") return null;
    const groups: Partial<Record<WikiPageType, WikiPageSummary[]>> = {};
    for (const page of filtered) {
      if (!groups[page.page_type]) groups[page.page_type] = [];
      groups[page.page_type]!.push(page);
    }
    return groups;
  }, [filtered, activeFilter]);

  return (
    <div className="wiki-page min-h-screen" style={{ backgroundColor: "var(--wiki-bg, #e8e3d9)" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="mb-8 text-center">
          <p style={{ fontSize: "11px", fontWeight: 600, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--wiki-accent, #b85c38)", marginBottom: "0.75rem" }}>
            Knowledge Base
          </p>
          <h1 style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 600, color: "var(--wiki-ink, #1c1a14)", marginBottom: "0.5rem" }}>
            The Wiki
          </h1>
          <p style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "1.1rem", fontStyle: "italic", color: "var(--wiki-ink-muted, #5c5848)" }}>
            Everything Jeromelu knows — players, teams, advisors, rounds.
          </p>
          <div style={{ width: 60, height: 1, background: "var(--wiki-accent, #b85c38)", margin: "1.5rem auto 0", opacity: 0.4 }} />
        </div>

        {/* Search + Filters */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-8 justify-center">
          <input
            type="text"
            placeholder="Search pages..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full sm:w-64 px-3 py-2 text-sm rounded-lg border focus:outline-none"
            style={{
              borderColor: "var(--wiki-border, rgba(28,26,20,0.12))",
              background: "var(--wiki-surface, #f0ebe2)",
              color: "var(--wiki-ink, #1c1a14)",
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
                  backgroundColor: activeFilter === tab.key ? "var(--wiki-accent-bg, #f0ddd5)" : "transparent",
                  color: activeFilter === tab.key ? "var(--wiki-accent, #b85c38)" : "var(--wiki-ink-faint, #9c9484)",
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Page grid — full width, no sidebar */}
        {activeFilter === "all" && grouped ? (
          Object.entries(grouped).map(([type, groupPages]) => {
            const config = TYPE_CONFIG[type as WikiPageType];
            const Icon = config?.icon || FileText;
            return (
              <div key={type} className="mb-8">
                <div className="flex items-center gap-2 mb-3">
                  <Icon size={16} style={{ color: "var(--wiki-accent, #b85c38)" }} />
                  <h2 style={{ fontSize: "11px", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--wiki-ink-faint, #9c9484)" }}>
                    {config?.label || type}
                  </h2>
                  <span style={{ fontSize: "12px", color: "var(--wiki-ink-faint, #9c9484)" }}>
                    ({groupPages!.length})
                  </span>
                </div>
                <PageGrid pages={groupPages!} />
              </div>
            );
          })
        ) : (
          <PageGrid pages={filtered} />
        )}

        {filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: "4rem 0", color: "var(--wiki-ink-faint, #9c9484)" }}>
            <FileText size={32} style={{ marginBottom: "0.75rem", opacity: 0.5 }} />
            <p style={{ fontSize: "14px" }}>No pages found.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function PageGrid({ pages }: { pages: WikiPageSummary[] }) {
  return (
    <div
      style={{
        display: "grid",
        gap: "1px",
        background: "var(--wiki-border, rgba(28,26,20,0.12))",
        border: "1px solid var(--wiki-border, rgba(28,26,20,0.12))",
      }}
      className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
    >
      {pages.map((page) => (
        <Link
          key={page.page_id}
          href={pageHref(page)}
          className="group block transition-colors"
          style={{ background: "var(--wiki-surface, #f0ebe2)", padding: "1.4rem" }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--wiki-bg, #e8e3d9)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "var(--wiki-surface, #f0ebe2)"; }}
        >
          <h3
            className="group-hover:underline"
            style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "1.1rem", fontWeight: 600, color: "var(--wiki-ink, #1c1a14)", marginBottom: "0.3rem" }}
          >
            {page.title}
          </h3>
          {page.summary && (
            <p className="line-clamp-2" style={{ fontSize: "13px", color: "var(--wiki-ink-muted, #5c5848)", marginBottom: "0.5rem", lineHeight: 1.5 }}>
              {page.summary}
            </p>
          )}
          <div className="flex items-center gap-2" style={{ fontSize: "11px", color: "var(--wiki-ink-faint, #9c9484)" }}>
            <Clock size={10} />
            <span>{formatRelative(page.updated_at)}</span>
            {page.status !== "published" && (
              <span style={{ fontSize: "10px", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", padding: "0.15rem 0.4rem", borderRadius: "2px", background: "var(--wiki-amber-bg, #f0e5c8)", color: "var(--wiki-amber, #8a6a20)" }}>
                {page.status}
              </span>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
