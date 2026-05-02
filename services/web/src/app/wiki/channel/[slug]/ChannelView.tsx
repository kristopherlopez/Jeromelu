"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  BellPlus,
  Calendar,
  CheckCircle2,
  Clock,
  Globe,
  Headphones,
  Instagram,
  Mic,
  PlayCircle,
  Radio,
  Sparkles,
  Youtube,
} from "lucide-react";
import type {
  WikiPageDetail,
  WikiPageSummary,
  WikiRevisionItem,
} from "../../wiki-data";
import type { ChannelEpisode } from "./episodes";
import "../../wiki.css";

/* ── Style tokens ── */

const v = {
  surface: "var(--wiki-surface)",
  bg: "var(--wiki-bg)",
  border: "var(--wiki-border)",
  borderStrong: "var(--wiki-border-strong)",
  ink: "var(--wiki-ink)",
  inkMuted: "var(--wiki-ink-muted)",
  inkFaint: "var(--wiki-ink-faint)",
  accent: "var(--wiki-accent)",
  accentBg: "var(--wiki-accent-bg)",
  amber: "var(--wiki-amber)",
  amberBg: "var(--wiki-amber-bg)",
  teal: "var(--wiki-teal)",
  tealBg: "var(--wiki-teal-bg)",
  purple: "var(--wiki-purple)",
  purpleBg: "var(--wiki-purple-bg)",
  serif: "var(--font-serif), Georgia, serif",
};

/* ── Helpers ── */

function initials(title: string, max = 2): string {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, max)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function prettifyTag(tag: string): string {
  return tag
    .replace(/[-_]+/g, " ")
    .replace(/\bnrlw\b/gi, "NRLW")
    .replace(/\bnrl\b/gi, "NRL")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const diff = Math.max(0, Date.now() - then);
  const min = Math.floor(diff / 60_000);
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

function formatMonthYear(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return "—";
  return d.toLocaleDateString("en-AU", { month: "short", year: "numeric" });
}

const PLATFORM_LABEL: Record<string, string> = {
  youtube: "YouTube",
  instagram: "Instagram",
  twitter: "Twitter",
  podcast: "Podcast",
  rss: "RSS",
};

function platformLabel(platform: string | null | undefined): string {
  if (!platform) return "Unknown";
  return PLATFORM_LABEL[platform.toLowerCase()] ?? prettifyTag(platform);
}

function PlatformIcon({
  platform,
  size = 14,
}: {
  platform: string | null | undefined;
  size?: number;
}) {
  if (!platform) return <Radio size={size} />;
  const k = platform.toLowerCase();
  if (k === "youtube") return <Youtube size={size} />;
  if (k === "instagram") return <Instagram size={size} />;
  if (k === "podcast") return <Headphones size={size} />;
  return <Radio size={size} />;
}

function deriveFormat(
  platform: string | null | undefined,
  tags: string[],
): string {
  const left = platformLabel(platform);
  const preferred = ["analysis", "opinion", "interviews", "previews", "review"];
  const pick = tags.find((t) =>
    preferred.some((p) => t.toLowerCase().includes(p)),
  );
  if (pick) return `${left} · ${prettifyTag(pick)}`;
  if (tags[0]) return `${left} · ${prettifyTag(tags[0])}`;
  return left;
}

// Tags → editorial phrases for the "What this voice covers" sidebar.
// Falls back to prettified tag if no mapping exists.
const COVERAGE_PHRASES: Record<string, string> = {
  analysis: "Tactical analysis",
  opinion: "Opinion & hot takes",
  nrlw: "NRLW coverage",
  previews: "Match previews & reviews",
  reviews: "Post-match reviews",
  interviews: "Player interviews & features",
  news: "NRL news & analysis",
  supercoach: "SuperCoach strategy",
  fantasy: "Fantasy tips & strategy",
  stats: "Stats & data",
  statistics: "Stats & data",
  humour: "Humour & banter",
  comedy: "Humour & banter",
  injuries: "Injury & casualty updates",
};

function coverageLineFor(tag: string): string {
  const k = tag.toLowerCase().replace(/[-_]+/g, "");
  return COVERAGE_PHRASES[k] ?? prettifyTag(tag);
}

function pageHref(p: { slug: string }): string {
  return `/wiki/channel/${p.slug}`;
}

/* ══════════════════════════════════════════════════════
   Top-level Channel view
   ══════════════════════════════════════════════════════ */

interface ChannelViewProps {
  page: WikiPageDetail;
  revisions: WikiRevisionItem[];
  relatedChannels: WikiPageSummary[];
  episodes: ChannelEpisode[];
}

export default function ChannelView({
  page,
  revisions,
  relatedChannels,
  episodes,
}: ChannelViewProps) {
  const channel = page.channel;
  const tags: string[] = useMemo(() => {
    if (channel?.tags?.length) return channel.tags;
    const t = page.metadata_json?.tags;
    if (Array.isArray(t)) return t.filter((x): x is string => typeof x === "string");
    return [];
  }, [channel, page.metadata_json]);

  const description =
    channel?.description ?? page.summary ?? "No description yet.";

  const related = useMemo(
    () => relatedChannels.filter((p) => p.slug !== page.slug).slice(0, 3),
    [relatedChannels, page.slug],
  );

  // Use related channels as visual stand-ins for the contributor stack since
  // we don't track per-voice contributors yet. Real data slots in cleanly when
  // it lands.
  const contributorStandIns = useMemo(
    () => relatedChannels.filter((p) => p.slug !== page.slug).slice(0, 5),
    [relatedChannels, page.slug],
  );

  return (
    <div className="wiki-page" data-theme="dark">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <BackLink />

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) minmax(260px, 320px)",
            gap: "1.5rem",
            alignItems: "start",
          }}
          className="channel-grid"
        >
        <main style={{ display: "flex", flexDirection: "column", gap: "1.25rem", minWidth: 0 }}>
          <HeroCard
            title={page.title}
            description={description}
            logoUrl={channel?.logo_url ?? null}
            tags={tags}
            channelUrl={channel?.url ?? null}
            platform={channel?.platform ?? null}
            networkAvatars={contributorStandIns}
          />
          <LatestEpisodesCard
            channelUrl={channel?.url ?? null}
            episodes={episodes}
          />
        </main>

        <aside style={{ display: "flex", flexDirection: "column", gap: "1rem", minWidth: 0 }}>
          <AboutCard
            platform={channel?.platform ?? null}
            tags={tags}
            createdProxyAt={channel?.last_polled_at ?? page.updated_at}
          />
          <CoversCard tags={tags} />
          <ContributorsCard avatars={contributorStandIns} />
          <RelatedVoicesCard related={related} />
        </aside>
        </div>

        <Footer revisions={revisions} updatedAt={page.updated_at} />
      </div>

      <style jsx>{`
        @media (max-width: 900px) {
          .channel-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

/* ── Back link ─────────────────────────────────────── */

function BackLink() {
  return (
    <Link
      href="/wiki?type=voices"
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
      <ArrowLeft size={12} /> All voices
    </Link>
  );
}

/* ── Hero card ─────────────────────────────────────── */

function HeroCard({
  title,
  description,
  logoUrl,
  tags,
  channelUrl,
  platform,
  networkAvatars,
}: {
  title: string;
  description: string;
  logoUrl: string | null;
  tags: string[];
  channelUrl: string | null;
  platform: string | null;
  networkAvatars: WikiPageSummary[];
}) {
  return (
    <section
      style={{
        background: v.surface,
        border: `1px solid ${v.border}`,
        borderRadius: 10,
        padding: "1.6rem",
        display: "grid",
        gridTemplateColumns: "auto minmax(0, 1fr) 180px",
        gap: "1.4rem",
        alignItems: "stretch",
      }}
      className="channel-hero"
    >
      <Logo logoUrl={logoUrl} title={title} size={88} />

      <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem", minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.55rem",
            flexWrap: "wrap",
          }}
        >
          <h1
            style={{
              fontFamily: v.serif,
              fontSize: "clamp(1.45rem, 2.3vw, 1.85rem)",
              fontWeight: 700,
              color: v.ink,
              lineHeight: 1.15,
              margin: 0,
            }}
          >
            {title}
          </h1>
          <span
            className="wiki-tag accent"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}
          >
            <Mic size={10} /> Voice
          </span>
        </div>

        <p
          style={{
            fontSize: "13.5px",
            color: v.inkMuted,
            lineHeight: 1.55,
            margin: 0,
          }}
        >
          {description}
        </p>

        {tags.length > 0 && (
          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
            {tags.slice(0, 6).map((t) => (
              <span key={t} className="wiki-tag accent">
                {prettifyTag(t)}
              </span>
            ))}
          </div>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.85rem",
            marginTop: "0.3rem",
            flexWrap: "wrap",
          }}
        >
          <FollowButton channelUrl={channelUrl} platform={platform} />
          <NetworkStrip avatars={networkAvatars} />
        </div>
      </div>

      <MicVisual />

      <style jsx>{`
        @media (max-width: 760px) {
          :global(.channel-hero) {
            grid-template-columns: auto minmax(0, 1fr) !important;
          }
          :global(.channel-hero .channel-mic) {
            display: none !important;
          }
        }
      `}</style>
    </section>
  );
}

function FollowButton({
  channelUrl,
  platform,
}: {
  channelUrl: string | null;
  platform: string | null;
}) {
  const Inner = (
    <>
      <BellPlus size={14} />
      Follow
    </>
  );
  const baseStyle = {
    display: "inline-flex",
    alignItems: "center",
    gap: "0.4rem",
    background: v.accent,
    color: "#fff",
    padding: "0.5rem 1.1rem",
    borderRadius: 999,
    fontSize: "13px",
    fontWeight: 600,
    textDecoration: "none",
    letterSpacing: "0.02em",
    border: "none",
    fontFamily: "inherit",
    cursor: channelUrl ? "pointer" : "default",
  } as const;

  if (channelUrl) {
    return (
      <a
        href={channelUrl}
        target="_blank"
        rel="noopener noreferrer"
        title={`Follow on ${platformLabel(platform)}`}
        style={baseStyle}
      >
        {Inner}
      </a>
    );
  }
  return (
    <span style={{ ...baseStyle, opacity: 0.65 }}>{Inner}</span>
  );
}

function NetworkStrip({ avatars }: { avatars: WikiPageSummary[] }) {
  const shown = avatars.slice(0, 4);
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.5rem",
      }}
      title="Other voices Jaromelu is tracking alongside this one"
    >
      <div style={{ display: "inline-flex" }}>
        {shown.map((a, i) => (
          <span
            key={a.page_id}
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              overflow: "hidden",
              border: `2px solid ${v.surface}`,
              marginLeft: i === 0 ? 0 : -8,
              background: v.bg,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "9px",
              fontWeight: 700,
              color: v.inkMuted,
            }}
          >
            {a.logo_url ? (
              <img
                src={a.logo_url}
                alt=""
                width={22}
                height={22}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                loading="lazy"
                referrerPolicy="no-referrer"
              />
            ) : (
              initials(a.title, 1)
            )}
          </span>
        ))}
      </div>
      <span style={{ fontSize: "12px", color: v.inkFaint, fontWeight: 500 }}>
        Tracked by Jaromelu
      </span>
    </div>
  );
}

function MicVisual() {
  // CSS-based stand-in for the reference's microphone photo. A warm radial
  // glow matching the wiki accent palette, with a Lucide Mic icon centred —
  // gives the hero the same "podcast-y" feel without an image asset.
  return (
    <div
      className="channel-mic"
      aria-hidden="true"
      style={{
        position: "relative",
        minHeight: 160,
        borderRadius: 8,
        background:
          "radial-gradient(120% 90% at 50% 35%, var(--wiki-accent-bg) 0%, transparent 70%), linear-gradient(180deg, rgba(0,0,0,0.18), rgba(0,0,0,0.05))",
        border: `1px solid ${v.border}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      {/* concentric "mesh" rings */}
      <span
        style={{
          position: "absolute",
          width: 130,
          height: 130,
          borderRadius: "50%",
          border: `1px solid ${v.accent}`,
          opacity: 0.18,
        }}
      />
      <span
        style={{
          position: "absolute",
          width: 90,
          height: 90,
          borderRadius: "50%",
          border: `1px solid ${v.accent}`,
          opacity: 0.32,
        }}
      />
      <Mic
        size={56}
        strokeWidth={1.5}
        style={{
          color: v.accent,
          filter: "drop-shadow(0 4px 16px rgba(184,92,56,0.35))",
        }}
      />
    </div>
  );
}

function Logo({
  logoUrl,
  title,
  size,
}: {
  logoUrl: string | null;
  title: string;
  size: number;
}) {
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt=""
        width={size}
        height={size}
        style={{
          width: size,
          height: size,
          borderRadius: 12,
          objectFit: "cover",
          background: v.bg,
          flexShrink: 0,
        }}
        loading="lazy"
        referrerPolicy="no-referrer"
      />
    );
  }
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 12,
        background: v.bg,
        color: v.inkMuted,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: v.serif,
        fontSize: size * 0.32,
        fontWeight: 700,
        border: `1px solid ${v.border}`,
        flexShrink: 0,
      }}
    >
      {initials(title, 2)}
    </div>
  );
}

/* ── Latest episodes card ─────────────────────────── */

function formatDuration(seconds: number | null): string {
  if (!seconds || seconds <= 0) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function LatestEpisodesCard({
  channelUrl,
  episodes,
}: {
  channelUrl: string | null;
  episodes: ChannelEpisode[];
}) {
  return (
    <section
      style={{
        background: v.surface,
        border: `1px solid ${v.border}`,
        borderRadius: 10,
        padding: "1.4rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "0.85rem",
        }}
      >
        <h2
          style={{
            fontFamily: v.serif,
            fontSize: "1.1rem",
            fontWeight: 700,
            color: v.ink,
            margin: 0,
          }}
        >
          Latest episodes
        </h2>
        {channelUrl && (
          <a
            href={channelUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: v.accent,
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.25rem",
            }}
          >
            See all episodes <ArrowRight size={11} />
          </a>
        )}
      </div>
      {episodes.length === 0 ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            padding: "2.25rem 1rem",
            color: v.inkFaint,
            gap: "0.6rem",
          }}
        >
          <PlayCircle size={28} style={{ opacity: 0.5 }} />
          <p style={{ fontSize: "13px", margin: 0, lineHeight: 1.5 }}>
            No episodes catalogued yet for this voice.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {episodes.map((ep, i) => (
            <EpisodeRow key={ep.source_id} ep={ep} index={i} />
          ))}
        </div>
      )}
    </section>
  );
}

function EpisodeRow({ ep, index }: { ep: ChannelEpisode; index: number }) {
  const router = useRouter();
  const duration = formatDuration(ep.duration_seconds);
  const ago = formatRelative(ep.published_at);

  // Only processed sources have a SourceDocument and render at /stream/[sourceId].
  // Pending rows fall back to opening the platform URL directly.
  const hasInternalPage = ep.ingestion_status === "completed";
  const onActivate = () => {
    if (hasInternalPage) {
      router.push(`/stream/${ep.source_id}`);
    } else if (ep.canonical_url) {
      window.open(ep.canonical_url, "_blank", "noopener,noreferrer");
    }
  };
  const isClickable = hasInternalPage || !!ep.canonical_url;

  return (
    <div
      role={isClickable ? "link" : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onClick={isClickable ? onActivate : undefined}
      onKeyDown={(e) => {
        if (isClickable && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onActivate();
        }
      }}
      style={{
        display: "grid",
        gridTemplateColumns: "92px minmax(0, 1fr) auto",
        gap: "0.85rem",
        alignItems: "center",
        padding: "0.7rem 0",
        borderTop: index === 0 ? "none" : `1px solid ${v.border}`,
        textDecoration: "none",
        color: "inherit",
        cursor: isClickable ? "pointer" : "default",
      }}
    >
      <div
        style={{
          width: 92,
          height: 52,
          borderRadius: 6,
          background: ep.thumbnail_url
            ? "transparent"
            : `linear-gradient(135deg, ${v.accentBg}, ${v.bg})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          border: `1px solid ${v.border}`,
          overflow: "hidden",
          position: "relative",
        }}
      >
        {ep.thumbnail_url ? (
          <img
            src={ep.thumbnail_url}
            alt=""
            width={92}
            height={52}
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
          <PlayCircle size={22} style={{ color: v.accent }} />
        )}
        {ep.thumbnail_url && (
          <PlayCircle
            size={20}
            style={{
              position: "absolute",
              color: "#fff",
              filter: "drop-shadow(0 1px 3px rgba(0,0,0,0.6))",
            }}
          />
        )}
      </div>
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: "13.5px",
            fontWeight: 600,
            color: v.ink,
            lineHeight: 1.35,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
          title={ep.title}
        >
          {ep.title}
        </div>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.6rem",
          color: v.inkFaint,
          fontSize: "11.5px",
        }}
      >
        <div style={{ textAlign: "right", lineHeight: 1.3 }}>
          <div style={{ fontWeight: 600, color: v.inkMuted }}>{duration}</div>
          <div>{ago || "—"}</div>
        </div>
        {ep.canonical_url ? (
          <a
            href={ep.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            title="Watch on YouTube"
            aria-label="Watch on YouTube"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              color: v.inkFaint,
              opacity: 0.7,
              textDecoration: "none",
            }}
          >
            <Youtube size={14} />
          </a>
        ) : (
          <span style={{ width: 14 }} aria-hidden="true" />
        )}
      </div>
    </div>
  );
}

/* ── About card ────────────────────────────────────── */

function AboutCard({
  platform,
  tags,
  createdProxyAt,
}: {
  platform: string | null;
  tags: string[];
  createdProxyAt: string | null;
}) {
  const rows: { icon: React.ReactNode; label: string; value: string }[] = [
    {
      icon: <Calendar size={13} />,
      label: "Created",
      value: formatMonthYear(createdProxyAt),
    },
    {
      icon: <Sparkles size={13} />,
      label: "Format",
      value: deriveFormat(platform, tags),
    },
    {
      icon: <Globe size={13} />,
      label: "Language",
      value: "English (AUS)",
    },
  ];

  return (
    <SidebarCard title="About this voice">
      <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem" }}>
        {rows.map((r) => (
          <div
            key={r.label}
            style={{
              display: "grid",
              gridTemplateColumns: "16px minmax(0, 1fr) auto",
              gap: "0.6rem",
              alignItems: "center",
              fontSize: "12.5px",
            }}
          >
            <span style={{ color: v.inkFaint, display: "inline-flex" }}>
              {r.icon}
            </span>
            <span style={{ color: v.inkFaint }}>{r.label}</span>
            <span style={{ color: v.ink, fontWeight: 500, textAlign: "right" }}>
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </SidebarCard>
  );
}

/* ── What this voice covers ────────────────────────── */

function CoversCard({ tags }: { tags: string[] }) {
  // De-dupe phrases (multiple tags can map to the same line) and cap at 4.
  const lines = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const t of tags) {
      const phrase = coverageLineFor(t);
      if (!seen.has(phrase)) {
        seen.add(phrase);
        out.push(phrase);
      }
    }
    return out.slice(0, 4);
  }, [tags]);

  return (
    <SidebarCard title="What this voice covers">
      {lines.length === 0 ? (
        <p style={{ fontSize: "12.5px", color: v.inkFaint, margin: 0 }}>
          Coverage will appear once the agent has read enough material.
        </p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            display: "flex",
            flexDirection: "column",
            gap: "0.55rem",
          }}
        >
          {lines.map((line) => (
            <li
              key={line}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.55rem",
                fontSize: "12.5px",
                color: v.ink,
              }}
            >
              <CheckCircle2
                size={13}
                style={{ color: v.accent, flexShrink: 0 }}
              />
              {line}
            </li>
          ))}
        </ul>
      )}
    </SidebarCard>
  );
}

/* ── Top contributors (avatar stack stand-in) ───── */

function ContributorsCard({ avatars }: { avatars: WikiPageSummary[] }) {
  if (avatars.length === 0) return null;
  return (
    <SidebarCard title="Top contributors">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.6rem",
        }}
        title="Contributor attribution lands when speaker diarisation ships"
      >
        <div style={{ display: "inline-flex" }}>
          {avatars.slice(0, 5).map((a, i) => (
            <span
              key={a.page_id}
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                overflow: "hidden",
                border: `2px solid ${v.surface}`,
                marginLeft: i === 0 ? 0 : -10,
                background: v.bg,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "10px",
                fontWeight: 700,
                color: v.inkMuted,
              }}
            >
              {a.logo_url ? (
                <img
                  src={a.logo_url}
                  alt=""
                  width={28}
                  height={28}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                />
              ) : (
                initials(a.title, 1)
              )}
            </span>
          ))}
        </div>
        <span style={{ fontSize: "11.5px", color: v.inkFaint, fontStyle: "italic" }}>
          attribution coming soon
        </span>
      </div>
    </SidebarCard>
  );
}

/* ── Related voices ────────────────────────────────── */

function RelatedVoicesCard({ related }: { related: WikiPageSummary[] }) {
  return (
    <SidebarCard
      title="Related voices"
      headerLink={{ href: "/wiki?type=voices", label: "See all" }}
    >
      {related.length === 0 ? (
        <p style={{ fontSize: "12.5px", color: v.inkFaint, margin: 0 }}>
          No other voices yet.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {related.map((p, i) => (
            <RelatedVoiceRow key={p.page_id} voice={p} firstRow={i === 0} />
          ))}
        </div>
      )}
    </SidebarCard>
  );
}

function RelatedVoiceRow({
  voice,
  firstRow,
}: {
  voice: WikiPageSummary;
  firstRow: boolean;
}) {
  const router = useRouter();
  const href = pageHref(voice);
  const channelUrl = voice.channel_url ?? null;

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
        display: "grid",
        gridTemplateColumns: "36px minmax(0, 1fr) auto",
        gap: "0.6rem",
        alignItems: "center",
        padding: "0.55rem 0",
        cursor: "pointer",
        borderTop: firstRow ? "none" : `1px solid ${v.border}`,
      }}
    >
      <Logo logoUrl={voice.logo_url ?? null} title={voice.title} size={36} />
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: "12.5px",
            fontWeight: 600,
            color: v.ink,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {voice.title}
        </div>
        <div
          style={{
            fontSize: "11px",
            color: v.inkFaint,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {voice.summary || platformLabel(voice.platform)}
        </div>
      </div>
      {channelUrl ? (
        <a
          href={channelUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: v.accent,
            textDecoration: "none",
            border: `1px solid ${v.accent}`,
            borderRadius: 999,
            padding: "0.2rem 0.7rem",
          }}
        >
          Follow
        </a>
      ) : (
        <span
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: v.inkFaint,
            border: `1px solid ${v.border}`,
            borderRadius: 999,
            padding: "0.2rem 0.7rem",
          }}
        >
          Follow
        </span>
      )}
    </div>
  );
}

/* ── Sidebar card primitive ───────────────────────── */

function SidebarCard({
  title,
  headerLink,
  children,
}: {
  title: string;
  headerLink?: { href: string; label: string };
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        background: v.surface,
        border: `1px solid ${v.border}`,
        borderRadius: 10,
        padding: "1.1rem 1.2rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "0.85rem",
        }}
      >
        <h3
          style={{
            fontSize: "11px",
            fontWeight: 600,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: v.inkFaint,
            margin: 0,
          }}
        >
          {title}
        </h3>
        {headerLink && (
          <Link
            href={headerLink.href}
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: v.accent,
              textDecoration: "none",
            }}
          >
            {headerLink.label}
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

/* ── Footer ────────────────────────────────────────── */

function Footer({
  revisions,
  updatedAt,
}: {
  revisions: WikiRevisionItem[];
  updatedAt: string;
}) {
  return (
    <footer
      style={{
        textAlign: "center",
        padding: "2.5rem 1rem 1rem",
        marginTop: "2rem",
        borderTop: `1px solid ${v.border}`,
        fontSize: "11px",
        color: v.inkFaint,
        letterSpacing: "0.04em",
      }}
    >
      <p style={{ margin: 0 }}>
        Voice page maintained by{" "}
        <strong style={{ color: v.inkMuted, fontWeight: 500 }}>Jaromelu</strong>{" "}
        — AI NRL SuperCoach Analyst
      </p>
      <p style={{ marginTop: "0.4rem", display: "inline-flex", gap: "0.4rem", alignItems: "center" }}>
        <Clock size={11} /> Last updated {formatRelative(updatedAt)}
        {revisions[0]?.summary && <> — {revisions[0].summary}</>}
      </p>
    </footer>
  );
}
