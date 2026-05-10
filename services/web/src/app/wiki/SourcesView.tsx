"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  ChevronDown,
  Clock,
  PenLine,
  Search,
  Video,
  Youtube,
} from "lucide-react";
import type { SourceListItem } from "@/lib/types";

type Voice = NonNullable<SourceListItem["voice"]>;

/* ── Style tokens (mirrors VoicesView) ── */

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

function timeAgo(iso: string | null): string {
  if (!iso) return "";
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

function youTubeVideoId(url: string | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    if (u.hostname === "youtu.be") {
      return u.pathname.slice(1) || null;
    }
    if (u.hostname.endsWith("youtube.com")) {
      const v = u.searchParams.get("v");
      if (v) return v;
      // Shorts / embed URLs: /shorts/<id>, /embed/<id>
      const parts = u.pathname.split("/").filter(Boolean);
      if ((parts[0] === "shorts" || parts[0] === "embed") && parts[1]) {
        return parts[1];
      }
    }
  } catch {
    // Invalid URL — fall through.
  }
  return null;
}

function thumbnailFor(canonicalUrl: string | null): string | null {
  const id = youTubeVideoId(canonicalUrl);
  return id ? `https://img.youtube.com/vi/${id}/mqdefault.jpg` : null;
}

function initials(title: string, max = 2): string {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, max)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function VoiceChip({ voice }: { voice: Voice }) {
  return (
    <Link
      href={`/wiki/channel/${voice.slug}`}
      // Defends against the card-level onClick which would otherwise router.push the source page.
      onClick={(e) => e.stopPropagation()}
      title={voice.name}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
        padding: "0.2rem 0.55rem 0.2rem 0.25rem",
        marginBottom: "0.4rem",
        borderRadius: 999,
        border: `1px solid ${v.border}`,
        background: v.bg,
        color: v.inkMuted,
        fontSize: "12px",
        fontWeight: 600,
        textDecoration: "none",
        maxWidth: "100%",
        minWidth: 0,
        alignSelf: "flex-start",
      }}
    >
      {voice.logo_url ? (
        <img
          src={voice.logo_url}
          alt=""
          width={20}
          height={20}
          style={{
            width: 20,
            height: 20,
            borderRadius: "50%",
            objectFit: "cover",
            background: v.surface,
            flexShrink: 0,
          }}
          loading="lazy"
          referrerPolicy="no-referrer"
        />
      ) : (
        <span
          style={{
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: v.surface,
            color: v.inkFaint,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "9px",
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {initials(voice.name, 2)}
        </span>
      )}
      <span
        style={{
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {voice.name}
      </span>
    </Link>
  );
}

type SortKey = "newest" | "oldest" | "most_claims" | "alpha";

function sortSources(items: SourceListItem[], sort: SortKey): SourceListItem[] {
  const out = [...items];
  switch (sort) {
    case "newest":
      return out.sort((a, b) => {
        if (!a.published_at) return 1;
        if (!b.published_at) return -1;
        return new Date(b.published_at).getTime() - new Date(a.published_at).getTime();
      });
    case "oldest":
      return out.sort((a, b) => {
        if (!a.published_at) return 1;
        if (!b.published_at) return -1;
        return new Date(a.published_at).getTime() - new Date(b.published_at).getTime();
      });
    case "most_claims":
      return out.sort((a, b) => b.claim_count - a.claim_count);
    case "alpha":
      return out.sort((a, b) => a.title.localeCompare(b.title));
  }
}

/* ══════════════════════════════════════════════════════
   Top-level Sources view
   ══════════════════════════════════════════════════════ */

export default function SourcesView({ sources }: { sources: SourceListItem[] }) {
  return (
    <>
      <SourcesHero />
      <SourcesIndex sources={sources} />
    </>
  );
}

/* ── Hero ─────────────────────────────────────────── */

function SourcesHero() {
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
        Sources
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
        Episodes, transcripts and claims feeding the Wiki.
      </p>
    </section>
  );
}

/* ── Sources index (search + sort + grid + load more) ── */

const PAGE_SIZE = 9;

function SourcesIndex({ sources }: { sources: SourceListItem[] }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("newest");
  const [visible, setVisible] = useState(PAGE_SIZE);

  const filtered = useMemo(() => {
    let result = sources;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (s) =>
          s.title.toLowerCase().includes(q) ||
          (s.creator_name?.toLowerCase().includes(q) ?? false),
      );
    }
    return sortSources(result, sort);
  }, [sources, search, sort]);

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
          All sources{" "}
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
        <SourcesControls
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
          No sources match.
        </div>
      ) : (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
          style={{ gap: "1rem" }}
        >
          {shown.map((s) => (
            <SourceCard key={s.source_id} source={s} />
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
            Load more sources
          </button>
        </div>
      )}
    </section>
  );
}

function SourcesControls({
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
          placeholder="Search sources…"
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
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="most_claims">Most claims</option>
          <option value="alpha">A–Z</option>
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

/* ── Source card ──────────────────────────────────── */

function SourceCard({ source }: { source: SourceListItem }) {
  const router = useRouter();
  const href = `/wiki/source/${source.source_id}`;
  const thumb = thumbnailFor(source.canonical_url);
  const isYouTube = Boolean(youTubeVideoId(source.canonical_url));
  const published = timeAgo(source.published_at);
  const hasClaims = source.claim_count > 0;

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
        {thumb ? (
          // YouTube thumbnails work well at 16:9; we crop to a square-ish
          // 84x84 to match the voice avatar footprint.
          <img
            src={thumb}
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
            {initials(source.creator_name || source.title, 2)}
          </div>
        )}
        {isYouTube && source.canonical_url && (
          <a
            href={source.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            title="Open on YouTube"
            aria-label="Open on YouTube in new tab"
            onClick={(e) => e.stopPropagation()}
            style={{
              marginTop: "auto",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 26,
              height: 26,
              borderRadius: "50%",
              background: "#ff0033",
              color: "#fff",
              flexShrink: 0,
              textDecoration: "none",
            }}
          >
            <Youtube size={15} strokeWidth={2.2} />
          </a>
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
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {source.title}
        </h3>
        {source.voice ? (
          <VoiceChip voice={source.voice} />
        ) : source.creator_name ? (
          <p
            style={{
              fontSize: "12px",
              color: v.inkMuted,
              lineHeight: 1.5,
              margin: 0,
              marginBottom: "0.4rem",
            }}
          >
            {source.creator_name}
          </p>
        ) : null}

        <div
          style={{
            marginTop: "auto",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            fontSize: "11px",
            color: v.inkFaint,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
              fontWeight: 600,
              color: hasClaims ? v.accent : v.inkFaint,
            }}
          >
            <PenLine size={11} />
            {source.claim_count} {source.claim_count === 1 ? "claim" : "claims"}
          </span>
          {published && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <Clock size={11} /> {published}
            </span>
          )}
          {!isYouTube && source.canonical_url && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <Video size={11} /> link
            </span>
          )}
          {!source.published_at && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <Calendar size={11} /> undated
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
