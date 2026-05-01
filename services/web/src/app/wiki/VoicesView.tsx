"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  Instagram,
  Search,
  ChevronDown,
  Youtube,
} from "lucide-react";
import type { WikiPageSummary, WikiPageType } from "./wiki-data";

/* ── Style tokens ── */

const v = {
  surface: "var(--wiki-surface)",
  bg: "var(--wiki-bg)",
  border: "var(--wiki-border)",
  ink: "var(--wiki-ink)",
  inkMuted: "var(--wiki-ink-muted)",
  inkFaint: "var(--wiki-ink-faint)",
  accent: "var(--wiki-accent)",
  accentBg: "var(--wiki-accent-bg)",
  amber: "var(--wiki-amber)",
  amberBg: "var(--wiki-amber-bg)",
  green: "var(--wiki-green)",
  greenBg: "var(--wiki-green-bg)",
  teal: "var(--wiki-teal)",
  tealBg: "var(--wiki-teal-bg)",
  purple: "var(--wiki-purple)",
  purpleBg: "var(--wiki-purple-bg)",
  red: "var(--wiki-red)",
  redBg: "var(--wiki-red-bg)",
  serif: "var(--font-serif), Georgia, serif",
};

/* ── Helpers ── */

function pageHref(p: { page_type: WikiPageType; slug: string }): string {
  return `/wiki/${p.page_type}/${p.slug}`;
}

function initials(title: string, max = 2): string {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, max)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function getTags(p: WikiPageSummary): string[] {
  const t = p.metadata_json?.tags;
  if (Array.isArray(t)) return t.filter((x): x is string => typeof x === "string");
  return [];
}

const BRAND_PALETTE = [
  { fg: v.accent, bg: v.accentBg },
  { fg: v.teal, bg: v.tealBg },
  { fg: v.amber, bg: v.amberBg },
  { fg: v.purple, bg: v.purpleBg },
  { fg: v.green, bg: v.greenBg },
  { fg: v.red, bg: v.redBg },
];

function brandColourFor(slug: string): { fg: string; bg: string } {
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash * 31 + slug.charCodeAt(i)) | 0;
  }
  return BRAND_PALETTE[Math.abs(hash) % BRAND_PALETTE.length];
}

type PlatformSpec = {
  label: string;
  icon: typeof Youtube;
  fg: string;
};

const PLATFORM_SPECS: Record<string, PlatformSpec> = {
  youtube: { label: "YouTube", icon: Youtube, fg: "#ff0033" },
  instagram: { label: "Instagram", icon: Instagram, fg: "#e1306c" },
};

function PlatformChip({
  platform,
  url,
}: {
  platform: string;
  url?: string | null;
}) {
  const spec = PLATFORM_SPECS[platform.toLowerCase()];
  if (!spec) return null;
  const Icon = spec.icon;
  const sharedStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 26,
    height: 26,
    borderRadius: "50%",
    background: spec.fg,
    color: "#fff",
    flexShrink: 0,
    textDecoration: "none",
  } as const;

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        title={`Open ${spec.label} channel`}
        aria-label={`Open ${spec.label} channel in new tab`}
        onClick={(e) => e.stopPropagation()}
        style={{ ...sharedStyle, cursor: "pointer" }}
      >
        <Icon size={15} strokeWidth={2.2} />
      </a>
    );
  }
  return (
    <span title={spec.label} aria-label={spec.label} style={sharedStyle}>
      <Icon size={15} strokeWidth={2.2} />
    </span>
  );
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const diff = Math.max(0, Date.now() - then);
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  const wk = Math.floor(day / 7);
  if (wk < 5) return `${wk}w ago`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(day / 365)}y ago`;
}

type SortKey = "active" | "alpha" | "newest" | "trusted";

function sortVoices(pages: WikiPageSummary[], sort: SortKey): WikiPageSummary[] {
  const out = [...pages];
  switch (sort) {
    case "alpha":
      return out.sort((a, b) => a.title.localeCompare(b.title));
    case "newest":
    case "active":
      return out.sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      );
    case "trusted":
      // No trust signal yet — fall back to alphabetical so the option is non-destructive.
      return out.sort((a, b) => a.title.localeCompare(b.title));
  }
}

/* ══════════════════════════════════════════════════════
   Top-level Voices view
   ══════════════════════════════════════════════════════ */

export default function VoicesView({ pages }: { pages: WikiPageSummary[] }) {
  return (
    <>
      <VoicesHero />
      <TrendingTakes voices={pages} />
      <VoicesIndex pages={pages} />
    </>
  );
}

/* ── Hero ─────────────────────────────────────────── */

function VoicesHero() {
  return (
    <section style={{ marginBottom: "2.5rem" }}>
      <Link
        href="/wiki"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.4rem",
          fontSize: "11px",
          fontWeight: 600,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: v.inkFaint,
          textDecoration: "none",
          marginBottom: "1.25rem",
        }}
      >
        <ArrowLeft size={12} /> Back to the Wiki
      </Link>
      <h1
        style={{
          fontFamily: v.serif,
          fontSize: "clamp(2rem, 4.4vw, 2.9rem)",
          fontWeight: 700,
          color: v.ink,
          lineHeight: 1.05,
          marginBottom: "0.5rem",
        }}
      >
        Voices
      </h1>
      <p
        style={{
          fontFamily: v.serif,
          fontSize: "1.1rem",
          fontStyle: "italic",
          color: v.inkMuted,
          lineHeight: 1.5,
          maxWidth: 560,
        }}
      >
        Channels and commentators shaping the NRL conversation.
      </p>
    </section>
  );
}

/* ── Trending takes (stubbed) ─────────────────────── */

type Take = {
  question: string;
  metric: string;
  metricLabel: string;
  detail: string;
  tone: "split" | "aligned";
  yesCount: number;
  noCount: number;
};

const STUB_TAKES: Take[] = [
  {
    question: "Is Broncos' middle fatigue a real problem?",
    metric: "8/8",
    metricLabel: "voices split",
    detail: "Half see structural cracks, half see a Round-7 blip.",
    tone: "split",
    yesCount: 4,
    noCount: 4,
  },
  {
    question: "Storm's edge attack is the key pressure point.",
    metric: "12",
    metricLabel: "voices align",
    detail: "Most analysts agree the right edge is the matchup advantage.",
    tone: "aligned",
    yesCount: 10,
    noCount: 2,
  },
];

const TONE_CONFIG: Record<Take["tone"], { fg: string; bg: string }> = {
  split: { fg: v.accent, bg: v.accentBg },
  aligned: { fg: v.teal, bg: v.tealBg },
};

function TrendingTakes({ voices }: { voices: WikiPageSummary[] }) {
  return (
    <section style={{ marginBottom: "2.5rem" }}>
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
        What&rsquo;s being said right now
      </div>
      <div
        className="grid grid-cols-1 md:grid-cols-2"
        style={{
          gap: "1rem",
          marginTop: "1rem",
        }}
      >
        {STUB_TAKES.map((take, i) => {
          // Slice a stable batch of voices per card, then split into yes / no.
          const slice = voices.slice(i * 5, i * 5 + 5);
          const yesAvatars = slice.slice(0, Math.min(3, take.yesCount));
          const noAvatars = slice
            .slice(Math.min(3, take.yesCount))
            .slice(0, Math.min(3, take.noCount));
          return (
            <TakeCard
              key={take.question}
              take={take}
              yesAvatars={yesAvatars}
              noAvatars={noAvatars}
            />
          );
        })}
      </div>
    </section>
  );
}

function TakeCard({
  take,
  yesAvatars,
  noAvatars,
}: {
  take: Take;
  yesAvatars: WikiPageSummary[];
  noAvatars: WikiPageSummary[];
}) {
  const tone = TONE_CONFIG[take.tone];
  return (
    <article
      style={{
        background: v.surface,
        border: `1px solid ${v.border}`,
        padding: "1.4rem",
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
      }}
    >
      <h3
        style={{
          fontFamily: v.serif,
          fontStyle: "italic",
          fontSize: "1.15rem",
          fontWeight: 600,
          color: v.ink,
          lineHeight: 1.35,
        }}
      >
        {take.question}
      </h3>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "1.25rem",
        }}
      >
        <ToneVisual tone={take.tone} fg={tone.fg} bg={tone.bg} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontFamily: v.serif,
              fontSize: "1.75rem",
              fontWeight: 700,
              color: tone.fg,
              lineHeight: 1,
              marginBottom: "0.25rem",
            }}
          >
            {take.metric}
          </div>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              letterSpacing: "0.08em",
              color: v.inkFaint,
              textTransform: "uppercase",
              marginBottom: "0.6rem",
            }}
          >
            {take.metricLabel}
          </div>
          <p
            style={{
              fontSize: "13px",
              color: v.inkMuted,
              lineHeight: 1.5,
            }}
          >
            {take.detail}
          </p>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: take.noCount > 0 ? "1fr 1fr" : "1fr",
          gap: "0.85rem",
          paddingTop: "0.85rem",
          borderTop: `1px solid ${v.border}`,
        }}
      >
        <SideStack
          label="Saying yes"
          count={take.yesCount}
          avatars={yesAvatars}
          colour={v.teal}
        />
        {take.noCount > 0 && (
          <SideStack
            label="Saying no"
            count={take.noCount}
            avatars={noAvatars}
            colour={v.red}
          />
        )}
      </div>

      <Link
        href="#"
        style={{
          marginTop: "auto",
          fontSize: "12px",
          fontWeight: 600,
          color: tone.fg,
          textDecoration: "none",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.3rem",
          letterSpacing: "0.02em",
        }}
      >
        Explore this narrative <ArrowRight size={12} />
      </Link>
    </article>
  );
}

function SideStack({
  label,
  count,
  avatars,
  colour,
}: {
  label: string;
  count: number;
  avatars: WikiPageSummary[];
  colour: string;
}) {
  const overflow = count - avatars.length;
  return (
    <div>
      <div
        style={{
          fontSize: "10px",
          fontWeight: 600,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: colour,
          marginBottom: "0.45rem",
        }}
      >
        {label} <span style={{ color: v.inkFaint, fontWeight: 500 }}>· {count}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
        {avatars.map((a) => {
          const c = brandColourFor(a.slug);
          return (
            <Link
              key={a.page_id}
              href={pageHref(a)}
              title={a.title}
              style={{
                width: 24,
                height: 24,
                borderRadius: "50%",
                background: c.bg,
                color: c.fg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "9px",
                fontWeight: 700,
                textDecoration: "none",
                border: `1px solid ${c.fg}`,
                overflow: "hidden",
              }}
            >
              {a.logo_url ? (
                <img
                  src={a.logo_url}
                  alt=""
                  width={24}
                  height={24}
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
                initials(a.title)
              )}
            </Link>
          );
        })}
        {overflow > 0 && (
          <span
            style={{
              fontSize: "11px",
              color: v.inkFaint,
              marginLeft: "0.3rem",
              fontWeight: 500,
            }}
          >
            +{overflow}
          </span>
        )}
      </div>
    </div>
  );
}

function ToneVisual({
  tone,
  fg,
  bg,
}: {
  tone: Take["tone"];
  fg: string;
  bg: string;
}) {
  if (tone === "split") {
    // Half-circle gauge split into two halves — visualises disagreement.
    return (
      <svg
        width="64"
        height="64"
        viewBox="0 0 64 64"
        aria-hidden="true"
        style={{ flexShrink: 0 }}
      >
        <circle
          cx="32"
          cy="32"
          r="28"
          fill={bg}
          stroke={fg}
          strokeWidth="1.5"
        />
        <path
          d="M 32 4 A 28 28 0 0 1 32 60 Z"
          fill={fg}
          opacity="0.55"
        />
        <line
          x1="32"
          y1="4"
          x2="32"
          y2="60"
          stroke={fg}
          strokeWidth="1.5"
        />
      </svg>
    );
  }
  // Aligned — a single rising arc with an arrow tip.
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <circle
        cx="32"
        cy="32"
        r="28"
        fill={bg}
        stroke={fg}
        strokeWidth="1.5"
      />
      <path
        d="M 16 44 L 30 30 L 38 36 L 50 22"
        fill="none"
        stroke={fg}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M 44 22 L 50 22 L 50 28"
        fill="none"
        stroke={fg}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/* ── Voices index (search + sort + grid + load more) ── */

const PAGE_SIZE = 9;

function VoicesIndex({ pages }: { pages: WikiPageSummary[] }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("active");
  const [visible, setVisible] = useState(PAGE_SIZE);

  const filtered = useMemo(() => {
    let result = pages;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          (p.summary?.toLowerCase().includes(q) ?? false) ||
          getTags(p).some((t) => t.toLowerCase().includes(q)),
      );
    }
    return sortVoices(result, sort);
  }, [pages, search, sort]);

  const shown = filtered.slice(0, visible);
  const hasMore = filtered.length > visible;

  return (
    <section style={{ marginBottom: "3rem" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
      >
        <h2
          style={{
            fontFamily: v.serif,
            fontSize: "1.4rem",
            fontWeight: 700,
            color: v.ink,
          }}
        >
          All voices{" "}
          <span
            style={{
              fontSize: "13px",
              fontWeight: 400,
              color: v.inkFaint,
              marginLeft: "0.4rem",
            }}
          >
            ({filtered.length})
          </span>
        </h2>
        <VoicesControls
          search={search}
          onSearch={(q) => {
            setSearch(q);
            setVisible(PAGE_SIZE);
          }}
          sort={sort}
          onSort={(s) => setSort(s)}
        />
      </div>

      {shown.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "3rem 0",
            color: v.inkFaint,
            fontSize: "14px",
          }}
        >
          No voices match.
        </div>
      ) : (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
          style={{ gap: "1rem" }}
        >
          {shown.map((p) => (
            <VoiceCard key={p.page_id} voice={p} />
          ))}
        </div>
      )}

      {hasMore && (
        <div style={{ marginTop: "1.5rem", textAlign: "center" }}>
          <button
            onClick={() => setVisible((n) => n + PAGE_SIZE)}
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: v.accent,
              background: "none",
              border: `1px solid ${v.border}`,
              borderRadius: 6,
              padding: "0.6rem 1.2rem",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Load more voices
          </button>
        </div>
      )}
    </section>
  );
}

function VoicesControls({
  search,
  onSearch,
  sort,
  onSort,
}: {
  search: string;
  onSearch: (s: string) => void;
  sort: SortKey;
  onSort: (s: SortKey) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
          background: v.surface,
          border: `1px solid ${v.border}`,
          borderRadius: 6,
          padding: "0.35rem 0.7rem",
        }}
      >
        <Search size={13} style={{ color: v.inkFaint }} />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search voices…"
          style={{
            border: "none",
            background: "transparent",
            outline: "none",
            fontSize: "13px",
            color: v.ink,
            fontFamily: "inherit",
            width: 160,
          }}
        />
      </div>
      <div
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
        }}
      >
        <select
          value={sort}
          onChange={(e) => onSort(e.target.value as SortKey)}
          style={{
            appearance: "none",
            WebkitAppearance: "none",
            background: v.surface,
            border: `1px solid ${v.border}`,
            borderRadius: 6,
            padding: "0.4rem 1.8rem 0.4rem 0.7rem",
            fontSize: "13px",
            color: v.inkMuted,
            cursor: "pointer",
            fontFamily: "inherit",
            outline: "none",
          }}
        >
          <option value="active">Recently active</option>
          <option value="alpha">A–Z</option>
          <option value="newest">Newest</option>
          <option value="trusted">Most trusted</option>
        </select>
        <ChevronDown
          size={13}
          style={{
            position: "absolute",
            right: 8,
            color: v.inkFaint,
            pointerEvents: "none",
          }}
        />
      </div>
    </div>
  );
}

/* ── Voice card ──────────────────────────────────── */

function VoiceCard({ voice }: { voice: WikiPageSummary }) {
  // Prefer the top-level platform from the API (sourced from channel.platform);
  // fall back to metadata_json.platform if a page sets it manually.
  const platform =
    voice.platform ??
    (typeof voice.metadata_json?.platform === "string"
      ? (voice.metadata_json.platform as string)
      : null);
  const updated = timeAgo(voice.updated_at);
  const router = useRouter();
  const href = pageHref(voice);

  // Card wrapper is a div (not <Link>) so the platform chip inside can be a
  // real <a target="_blank"> without producing invalid nested anchors.
  // Browser HTML repair on <a><a> moves the inner anchor out, breaking
  // stopPropagation and causing the chip click to fall through to the card link.
  return (
    <div
      role="link"
      tabIndex={0}
      onClick={() => router.push(href)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          router.push(href);
        }
      }}
      style={{
        display: "flex",
        gap: "1.1rem",
        background: v.surface,
        border: `1px solid ${v.border}`,
        borderRadius: 8,
        padding: "1.1rem",
        color: "inherit",
        cursor: "pointer",
        transition: "border-color 0.15s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = v.accent;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--wiki-border)";
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          gap: "0.75rem",
          flexShrink: 0,
        }}
      >
        {voice.logo_url ? (
          <img
            src={voice.logo_url}
            alt=""
            width={84}
            height={84}
            style={{
              width: 84,
              height: 84,
              borderRadius: 6,
              objectFit: "cover",
              background: v.bg,
            }}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div
            style={{
              width: 84,
              height: 84,
              borderRadius: 6,
              background: v.bg,
              color: v.inkMuted,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: v.serif,
              fontSize: "1.4rem",
              fontWeight: 700,
              border: `1px solid ${v.border}`,
            }}
          >
            {initials(voice.title, 2)}
          </div>
        )}
        {platform && (
          <div
            style={{
              marginTop: "auto",
              display: "flex",
              alignItems: "center",
              gap: "0.45rem",
            }}
          >
            <PlatformChip platform={platform} url={voice.channel_url} />
          </div>
        )}
      </div>

      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <h3
          style={{
            fontFamily: v.serif,
            fontSize: "1.15rem",
            fontWeight: 700,
            color: v.ink,
            lineHeight: 1.25,
            margin: 0,
            marginBottom: "0.35rem",
          }}
        >
          {voice.title}
        </h3>
        <p
          style={{
            fontSize: "13px",
            color: v.inkMuted,
            lineHeight: 1.5,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            margin: 0,
            flex: 1,
          }}
        >
          {voice.summary || "No summary yet."}
        </p>

        <div
          style={{
            marginTop: "0.75rem",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            fontSize: "11px",
            color: v.inkFaint,
            flexWrap: "wrap",
          }}
        >
          {updated && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <Clock size={11} /> {updated}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
