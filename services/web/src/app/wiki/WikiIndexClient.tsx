"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Clock,
  FileText,
  Users,
  Radio,
  Mic,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  X,
  Info,
  Send,
} from "lucide-react";
import type { WikiPageSummary, WikiPageType } from "./wiki-data";
import VoicesView from "./VoicesView";
import PlayersIndexView from "./PlayersIndexView";
import "./wiki.css";

/* ── Constants ── */

const ITEMS_PER_PAGE = 30;

// Voices is a virtual tab that combines advisor + channel pages.
const VOICES_TYPES: WikiPageType[] = ["advisor", "channel"];

type EntityKey = "player" | "team" | "voices" | "source";

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

function pagesByEntity(pages: WikiPageSummary[], key: EntityKey): WikiPageSummary[] {
  if (key === "voices") return pages.filter((p) => VOICES_TYPES.includes(p.page_type));
  // "source" is not a wiki page_type — sources live at /wiki/source backed by /api/sources.
  if (key === "source") return [];
  return pages.filter((p) => p.page_type === key);
}

function initials(title: string): string {
  return title
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
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
   Top-level component — renders dashboard or entity view
   ══════════════════════════════════════════════════════ */

interface WikiIndexClientProps {
  pages: WikiPageSummary[];
  sourceCount?: number;
  initialType?: string;
}

// "source" is intentionally excluded — it has its own /wiki/source route, not a virtual ?type= filter.
const VALID_TYPES: EntityKey[] = ["player", "team", "voices"];

export default function WikiIndexClient({
  pages,
  sourceCount = 0,
  initialType,
}: WikiIndexClientProps) {
  const filterKey = (VALID_TYPES as string[]).includes(initialType ?? "")
    ? (initialType as EntityKey)
    : null;

  const filtered = useMemo(() => {
    if (!filterKey) return pages;
    return pagesByEntity(pages, filterKey);
  }, [pages, filterKey]);

  return (
    <div className="min-h-screen">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {filterKey ? (
          <EntityView entityKey={filterKey} pages={filtered} />
        ) : (
          <DashboardView pages={pages} sourceCount={sourceCount} />
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Entity view — reached via /wiki?type=<entity>
   ══════════════════════════════════════════════════════ */

function EntityView({
  entityKey,
  pages,
}: {
  entityKey: EntityKey;
  pages: WikiPageSummary[];
}) {
  if (entityKey === "voices") {
    return <VoicesView pages={pages} />;
  }
  if (entityKey === "player") {
    return <PlayersIndexView pages={pages} />;
  }

  const label = ENTITY_CONFIG[entityKey].label;

  return (
    <>
      <Link
        href="/wiki"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.4rem",
          fontSize: "12px",
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: v.inkFaint,
          textDecoration: "none",
          marginBottom: "1.5rem",
        }}
      >
        <ArrowLeft size={14} /> Back to the Wiki
      </Link>
      <h1
        style={{
          fontFamily: v.serif,
          fontSize: "clamp(1.8rem, 4vw, 2.4rem)",
          fontWeight: 700,
          color: v.ink,
          lineHeight: 1.1,
          marginBottom: "0.4rem",
        }}
      >
        {label}
      </h1>
      <p
        style={{
          fontSize: "14px",
          color: v.inkFaint,
          marginBottom: "2rem",
        }}
      >
        {pages.length} {pages.length === 1 ? "page" : "pages"}
      </p>
      <PaginatedGrid pages={pages} />
      {pages.length === 0 && (
        <div
          style={{
            textAlign: "center",
            padding: "4rem 0",
            color: v.inkFaint,
          }}
        >
          <FileText size={32} style={{ marginBottom: "0.75rem", opacity: 0.5 }} />
          <p style={{ fontSize: "14px" }}>No pages found.</p>
        </div>
      )}
    </>
  );
}

/* ══════════════════════════════════════════════════════
   Dashboard — the landing page
   ══════════════════════════════════════════════════════ */

function DashboardView({
  pages,
  sourceCount,
}: {
  pages: WikiPageSummary[];
  sourceCount: number;
}) {
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <>
      <Hero onAboutClick={() => setAboutOpen(true)} />
      <ExploreByEntity pages={pages} sourceCount={sourceCount} />
      <AskJaromelu />
      <HowItConnects />
      <DashboardFooter />
      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} />}
    </>
  );
}

/* ── Hero ─────────────────────────────────────────────── */

function Hero({ onAboutClick }: { onAboutClick: () => void }) {
  return (
    <section
      style={{
        position: "relative",
        marginBottom: "2.25rem",
      }}
    >
      <button
        onClick={onAboutClick}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          display: "inline-flex",
          alignItems: "center",
          gap: "0.35rem",
          fontSize: "12px",
          fontWeight: 500,
          color: v.inkFaint,
          background: "none",
          border: "none",
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        <Info size={13} /> About the Wiki
      </button>
      <div
        className="grid grid-cols-1 md:grid-cols-[1.7fr_1fr]"
        style={{
          gap: "2rem",
          alignItems: "center",
        }}
      >
        <div>
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
              fontSize: "clamp(2rem, 4.4vw, 2.9rem)",
              fontWeight: 700,
              color: v.ink,
              lineHeight: 1.08,
              marginBottom: "0.85rem",
              maxWidth: 560,
            }}
          >
            Explore the knowledge behind Jaromelu.
          </h1>
          <p
            style={{
              fontFamily: v.serif,
              fontSize: "1.1rem",
              fontStyle: "italic",
              color: v.inkMuted,
              lineHeight: 1.5,
              maxWidth: 520,
            }}
          >
            Players, teams, voices and sources — connected by context.
          </p>
        </div>
        <AmbientGraph />
      </div>
    </section>
  );
}

/* ── Ambient graph (decorative, NON-INTERACTIVE) ── */

function AmbientGraph() {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "relative",
        width: "100%",
        height: 220,
        pointerEvents: "none",
      }}
    >
      <svg
        viewBox="0 0 400 280"
        width="100%"
        height="100%"
        style={{ overflow: "visible" }}
      >
        <defs>
          <radialGradient id="centreGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--wiki-accent)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--wiki-accent)" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Faint connecting lines */}
        <g stroke="var(--wiki-accent)" strokeWidth="1" opacity="0.25" fill="none">
          <line x1="200" y1="140" x2="200" y2="40" />
          <line x1="200" y1="140" x2="80" y2="140" />
          <line x1="200" y1="140" x2="320" y2="140" />
          <line x1="200" y1="140" x2="200" y2="240" />
        </g>

        {/* Centre glow */}
        <circle cx="200" cy="140" r="48" fill="url(#centreGlow)" />
        <circle
          cx="200"
          cy="140"
          r="9"
          fill="var(--wiki-accent)"
          opacity="0.85"
        >
          <animate
            attributeName="r"
            values="9;11;9"
            dur="3.6s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="opacity"
            values="0.85;0.6;0.85"
            dur="3.6s"
            repeatCount="indefinite"
          />
        </circle>

        {/* Satellites */}
        <SatelliteNode cx={200} cy={40} label="Players" />
        <SatelliteNode cx={80} cy={140} label="Teams" />
        <SatelliteNode cx={320} cy={140} label="Voices" />
        <SatelliteNode cx={200} cy={240} label="Sources" />
      </svg>
    </div>
  );
}

function SatelliteNode({
  cx,
  cy,
  label,
}: {
  cx: number;
  cy: number;
  label: string;
}) {
  return (
    <g>
      <circle
        cx={cx}
        cy={cy}
        r="5"
        fill="var(--wiki-surface)"
        stroke="var(--wiki-accent)"
        strokeWidth="1.5"
      />
      <text
        x={cx}
        y={cy + 22}
        textAnchor="middle"
        fontSize="11"
        fontWeight="600"
        fill="var(--wiki-ink-muted)"
        style={{ letterSpacing: "0.04em" }}
      >
        {label}
      </text>
    </g>
  );
}

/* ── About modal ────────────────────────────────────── */

function AboutModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="About the Wiki"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: "1rem",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: v.surface,
          border: `1px solid ${v.border}`,
          padding: "2rem",
          maxWidth: 480,
          width: "100%",
          position: "relative",
        }}
      >
        <button
          onClick={onClose}
          aria-label="Close"
          style={{
            position: "absolute",
            top: "0.85rem",
            right: "0.85rem",
            background: "none",
            border: "none",
            color: v.inkFaint,
            cursor: "pointer",
            padding: "0.25rem",
          }}
        >
          <X size={16} />
        </button>
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
          About the Wiki
        </div>
        <h2
          style={{
            fontFamily: v.serif,
            fontSize: "1.6rem",
            fontWeight: 700,
            color: v.ink,
            lineHeight: 1.2,
            marginBottom: "1rem",
          }}
        >
          A living knowledge base of NRL SuperCoach.
        </h2>
        <div
          style={{
            fontSize: "14px",
            color: v.inkMuted,
            lineHeight: 1.6,
          }}
        >
          <p style={{ marginBottom: "0.85rem" }}>
            Jaromelu maintains pages on every player, team and voice — and
            indexes the sources behind them, all connected so you can move
            between them by context.
          </p>
          <p style={{ marginBottom: "0.85rem" }}>
            Browse by entity to drop into a category, or use{" "}
            <strong style={{ color: v.ink }}>Ask Jaromelu</strong> for
            quick, scoped questions. For deeper, open-ended chat, head to{" "}
            <strong style={{ color: v.ink }}>Ask Me</strong>.
          </p>
          <p style={{ margin: 0 }}>
            New insights are added daily by the crew.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Explore by Entity ─────────────────────────────── */

const ENTITY_CONFIG: Record<
  EntityKey,
  {
    label: string;
    singular: string;
    icon: typeof FileText;
    copy: string;
    accent: string;
    accentBg: string;
  }
> = {
  player: {
    label: "Players",
    singular: "player",
    icon: Users,
    copy: "Profiles, form and value calls.",
    accent: v.teal,
    accentBg: v.tealBg,
  },
  team: {
    label: "Teams",
    singular: "team",
    icon: FileText,
    copy: "Squads, structures and edges.",
    accent: v.accent,
    accentBg: v.accentBg,
  },
  voices: {
    label: "Voices",
    singular: "voice",
    icon: Mic,
    copy: "Channels and the people behind them.",
    accent: v.purple,
    accentBg: v.purpleBg,
  },
  source: {
    label: "Sources",
    singular: "source",
    icon: Radio,
    copy: "Episodes, transcripts and claims.",
    accent: v.amber,
    accentBg: v.amberBg,
  },
};

const ENTITY_ORDER: EntityKey[] = ["player", "team", "voices", "source"];

function ExploreByEntity({
  pages,
  sourceCount,
}: {
  pages: WikiPageSummary[];
  sourceCount: number;
}) {
  return (
    <section style={{ marginBottom: "2.5rem" }}>
      <SectionLabel>Explore by Entity</SectionLabel>
      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
        style={{
          gap: "1rem",
          marginTop: "1.25rem",
        }}
      >
        {ENTITY_ORDER.map((key) => {
          // Sources don't live in the wiki pages table — count comes from /api/sources.
          const matched = pagesByEntity(pages, key);
          const samples = matched.slice(0, 4);
          const total = key === "source" ? sourceCount : matched.length;
          return (
            <EntityCard
              key={key}
              entityKey={key}
              samples={samples}
              total={total}
            />
          );
        })}
      </div>
    </section>
  );
}

function EntityCard({
  entityKey,
  samples,
  total,
}: {
  entityKey: EntityKey;
  samples: WikiPageSummary[];
  total: number;
}) {
  const cfg = ENTITY_CONFIG[entityKey];
  const Icon = cfg.icon;
  // Sources have a real route; everything else uses the dashboard's virtual ?type= filter.
  const browseHref = entityKey === "source" ? "/wiki/source" : `/wiki?type=${entityKey}`;

  return (
    <div
      style={{
        background: cfg.accentBg,
        border: `1px solid ${cfg.accent}`,
        borderRadius: 6,
        padding: "1.6rem 1.4rem",
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
      }}
    >
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.7rem",
            marginBottom: "0.85rem",
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: "50%",
              background: "rgba(255,255,255,0.08)",
              color: cfg.accent,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: `1px solid ${cfg.accent}`,
              flexShrink: 0,
            }}
          >
            <Icon size={17} />
          </div>
          <Link
            href={browseHref}
            style={{
              fontFamily: v.serif,
              fontSize: "1.35rem",
              fontWeight: 700,
              color: cfg.accent,
              lineHeight: 1.1,
              textDecoration: "none",
            }}
          >
            {cfg.label}
          </Link>
        </div>
        <p
          style={{
            fontSize: "13px",
            color: v.inkMuted,
            lineHeight: 1.45,
            minHeight: "2.9em",
          }}
        >
          {cfg.copy}
        </p>
      </div>

      <div>
        <div
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: cfg.accent,
            marginBottom: "0.5rem",
          }}
        >
          {total} {total === 1 ? cfg.singular : cfg.label.toLowerCase()}
        </div>
        {samples.length > 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              flexWrap: "wrap",
            }}
          >
            {samples.map((s) => (
              <Link
                key={s.page_id}
                href={pageHref(s)}
                title={s.title}
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  background: "rgba(0,0,0,0.18)",
                  color: cfg.accent,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "10px",
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  textDecoration: "none",
                  border: `1px solid ${cfg.accent}`,
                  overflow: "hidden",
                }}
              >
                {s.logo_url ? (
                  <img
                    src={s.logo_url}
                    alt=""
                    width={30}
                    height={30}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      display: "block",
                    }}
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  initials(s.title)
                )}
              </Link>
            ))}
            {total > samples.length && (
              <span
                style={{
                  fontSize: "11px",
                  color: cfg.accent,
                  marginLeft: "0.4rem",
                  fontWeight: 600,
                }}
              >
                +{total - samples.length}
              </span>
            )}
          </div>
        )}
      </div>

      <Link
        href={browseHref}
        style={{
          marginTop: "auto",
          fontSize: "12px",
          fontWeight: 600,
          color: cfg.accent,
          textDecoration: "none",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.3rem",
        }}
      >
        Browse all {cfg.label.toLowerCase()} <ArrowRight size={12} />
      </Link>
    </div>
  );
}

/* ── Ask Jaromelu ──────────────────────────────────── */

type AskScope = "general" | EntityKey;

const ASK_CHIPS: Record<AskScope, string[]> = {
  general: [
    "What changed today?",
    "Who's trending right now?",
    "Cheap value picks",
    "Trade targets this week",
    "Bye-round planning",
    "Captain options",
    "Watchlist for next week",
    "Most owned vs. most valuable",
  ],
  player: [
    "Top scoring forwards this week",
    "Best HFB form right now",
    "Players returning from injury",
    "Breakeven movers",
    "Cheap rookies starting",
    "Captain options",
    "Players to trade out",
  ],
  team: [
    "Strongest forward packs",
    "Teams under pressure",
    "Best home record",
    "Travel-affected teams",
    "Defensive struggles",
    "Form lines into this round",
  ],
  voices: [
    "Most trusted voices right now",
    "Recent calls vs. reality",
    "Best podcasts this week",
    "New voices added",
    "Trust-score movers",
  ],
  source: [
    "Latest episodes ingested",
    "Most-cited sources this week",
    "New transcripts ready",
    "Highest-claim episodes",
    "Sources covering injuries",
  ],
};

function AskJaromelu() {
  const router = useRouter();
  const [chipOffset, setChipOffset] = useState(0);
  const [question, setQuestion] = useState("");
  const [submitted, setSubmitted] = useState<string | null>(null);

  const allChips = ASK_CHIPS.general;
  const chips = useMemo(() => {
    const start = chipOffset % allChips.length;
    return [...allChips.slice(start), ...allChips.slice(0, start)].slice(0, 5);
  }, [allChips, chipOffset]);

  const submit = (q: string) => {
    if (!q.trim()) return;
    setSubmitted(q.trim());
  };

  const continueToAskMe = () => {
    const q = submitted ?? question;
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    router.push(`/ask?${params.toString()}`);
  };

  const reset = () => {
    setSubmitted(null);
    setQuestion("");
  };

  return (
    <section
      style={{
        marginBottom: "3rem",
        padding: "1.75rem 0",
        borderTop: `1px solid ${v.border}`,
        borderBottom: `1px solid ${v.border}`,
      }}
    >
      <SectionLabel>Ask Jaromelu</SectionLabel>
      <SectionTitle>What do you want to know?</SectionTitle>

      {/* Chips */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          alignItems: "center",
          marginTop: "1.25rem",
          marginBottom: "1rem",
        }}
      >
        {chips.map((c) => (
          <button
            key={c}
            onClick={() => submit(c)}
            style={{
              fontSize: "13px",
              padding: "0.45rem 0.85rem",
              borderRadius: 999,
              border: `1px solid ${v.border}`,
              background: v.surface,
              color: v.ink,
              cursor: "pointer",
              fontFamily: "inherit",
              transition: "background 0.15s, border-color 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = v.accentBg;
              e.currentTarget.style.borderColor = v.accent;
              e.currentTarget.style.color = v.accent;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = v.surface;
              e.currentTarget.style.borderColor = v.border;
              e.currentTarget.style.color = v.ink;
            }}
          >
            {c}
          </button>
        ))}
        <button
          onClick={() => setChipOffset((o) => o + 5)}
          aria-label="Refresh suggestions"
          style={{
            width: 30,
            height: 30,
            borderRadius: "50%",
            border: `1px solid ${v.border}`,
            background: v.surface,
            color: v.inkFaint,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
        style={{
          display: "flex",
          gap: "0.5rem",
          alignItems: "center",
          background: v.surface,
          border: `1px solid ${v.border}`,
          borderRadius: 8,
          padding: "0.4rem 0.4rem 0.4rem 1rem",
        }}
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Or type your own question…"
          style={{
            flex: 1,
            border: "none",
            background: "transparent",
            outline: "none",
            fontSize: "14px",
            color: v.ink,
            fontFamily: "inherit",
          }}
        />
        <button
          type="submit"
          aria-label="Ask"
          disabled={!question.trim()}
          style={{
            width: 34,
            height: 34,
            borderRadius: 6,
            border: "none",
            background: question.trim() ? v.accent : v.border,
            color: "white",
            cursor: question.trim() ? "pointer" : "default",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Send size={14} />
        </button>
      </form>

      {/* Answer block */}
      {submitted && (
        <div
          style={{
            marginTop: "1.25rem",
            padding: "1.25rem 1.4rem",
            background: v.surface,
            border: `1px solid ${v.border}`,
            borderLeft: `3px solid ${v.accent}`,
          }}
        >
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: v.inkFaint,
              marginBottom: "0.4rem",
            }}
          >
            You asked
          </div>
          <div
            style={{
              fontSize: "15px",
              color: v.ink,
              fontWeight: 500,
              marginBottom: "0.75rem",
            }}
          >
            {submitted}
          </div>
          <p
            style={{
              fontSize: "14px",
              color: v.inkMuted,
              lineHeight: 1.6,
              marginBottom: "1rem",
            }}
          >
            Jaromelu&rsquo;s inline answer engine is on its way. In the
            meantime, take this question to{" "}
            <strong style={{ color: v.ink }}>Ask Me</strong> for a full
            response.
          </p>
          <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
            <button
              onClick={continueToAskMe}
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: v.accent,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontFamily: "inherit",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
              }}
            >
              Continue in Ask Me <ArrowRight size={13} />
            </button>
            <button
              onClick={reset}
              style={{
                fontSize: "12px",
                color: v.inkFaint,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              Ask another
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

/* ── How it Connects ──────────────────────────────── */

function HowItConnects() {
  const stages: { key: EntityKey; caption: string }[] = [
    { key: "player", caption: "Who they are." },
    { key: "team", caption: "How they play." },
    { key: "voices", caption: "What it means." },
    { key: "source", caption: "Where it came from." },
  ];

  return (
    <section style={{ marginBottom: "3rem", paddingTop: "0.5rem" }}>
      <SectionLabel>How it Connects</SectionLabel>
      <SectionTitle>Everything is connected.</SectionTitle>
      <SectionSubtitle>
        Players sit inside teams, voices interpret the signal, and every claim
        traces back to a source. The same pages, four lenses.
      </SectionSubtitle>

      <div
        aria-hidden="true"
        style={{
          marginTop: "2rem",
          padding: "2rem 1rem",
          background: v.surface,
          border: `1px solid ${v.border}`,
          position: "relative",
        }}
      >
        {/* Connecting line */}
        <div
          style={{
            position: "absolute",
            top: "calc(2rem + 22px)",
            left: "12%",
            right: "12%",
            height: 1,
            background: v.border,
          }}
        />
        <div
          className="grid"
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${stages.length}, 1fr)`,
            gap: "0.5rem",
            position: "relative",
          }}
        >
          {stages.map(({ key, caption }) => {
            const cfg = ENTITY_CONFIG[key];
            const Icon = cfg.icon;
            return (
              <div
                key={key}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  textAlign: "center",
                  gap: "0.5rem",
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    background: cfg.accentBg,
                    color: cfg.accent,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: `1px solid ${v.border}`,
                    position: "relative",
                    zIndex: 1,
                  }}
                >
                  <Icon size={18} />
                </div>
                <div
                  style={{
                    fontFamily: v.serif,
                    fontSize: "1rem",
                    fontWeight: 700,
                    color: v.ink,
                  }}
                >
                  {cfg.label}
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: v.inkFaint,
                    lineHeight: 1.4,
                    maxWidth: 120,
                  }}
                >
                  {caption}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ marginTop: "1.25rem", textAlign: "right" }}>
        <Link
          href="/wiki/map"
          style={{
            fontSize: "13px",
            fontWeight: 600,
            color: v.accent,
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
          }}
        >
          Open the map <ArrowRight size={13} />
        </Link>
      </div>
    </section>
  );
}

/* ── Footer ───────────────────────────────────────── */

function DashboardFooter() {
  return (
    <footer
      style={{
        marginTop: "1rem",
        paddingTop: "2rem",
        borderTop: `1px solid ${v.border}`,
        display: "flex",
        gap: "0.75rem",
      }}
      className="flex-col items-center text-center sm:flex-row sm:items-center sm:justify-between sm:text-left"
    >
      <span
        style={{
          fontSize: "12px",
          color: v.inkFaint,
          letterSpacing: "0.04em",
        }}
      >
        New insights added daily by the crew.
      </span>
      <Link
        href="/pulse"
        style={{
          fontSize: "12px",
          fontWeight: 600,
          color: v.accent,
          textDecoration: "none",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.35rem",
        }}
      >
        See latest updates in Live Pulse <ArrowRight size={12} />
      </Link>
    </footer>
  );
}

/* ══════════════════════════════════════════════════════
   Editorial primitives
   ══════════════════════════════════════════════════════ */

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

/* ══════════════════════════════════════════════════════
   Paginated grid — for teams, rounds, voices
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
        >
          <div className="flex items-start gap-3" style={{ marginBottom: "0.3rem" }}>
            {page.logo_url && (
              // Channel avatar (YouTube thumbnail / podcast cover art / etc.).
              // Plain <img> rather than next/image since YouTube's CDN
              // (yt3.ggpht.com) isn't pre-allowlisted and the perf cost is
              // negligible for a 40px thumbnail in a list view.
              <img
                src={page.logo_url}
                alt=""
                width={40}
                height={40}
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 6,
                  flexShrink: 0,
                  objectFit: "cover",
                  background: v.border,
                }}
                loading="lazy"
                referrerPolicy="no-referrer"
              />
            )}
            <h3
              className="group-hover:underline"
              style={{
                fontFamily: v.serif,
                fontSize: "1.1rem",
                fontWeight: 700,
                color: v.ink,
                marginBottom: 0,
                flex: 1,
              }}
            >
              {page.title}
            </h3>
          </div>
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
