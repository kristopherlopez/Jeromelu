"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Users,
  TrendingUp,
  CheckCircle2,
  Sparkles,
  Mic,
  RefreshCw,
  Send,
  ChevronDown,
  DollarSign,
  MapPin,
  Activity,
  Clock,
  X,
  Search,
} from "lucide-react";
import type { WikiPageSummary } from "./wiki-data";
import "./wiki.css";

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

function pageHref(p: WikiPageSummary): string {
  return `/wiki/${p.page_type}/${p.slug}`;
}

function getMetaString(p: WikiPageSummary, key: string): string | null {
  const val = p.metadata_json?.[key];
  return typeof val === "string" ? val : null;
}

function getMetaNumber(p: WikiPageSummary, key: string): number | null {
  const val = p.metadata_json?.[key];
  return typeof val === "number" ? val : null;
}

function initials(title: string): string {
  return title
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function daysSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

function formatPrice(p: number): string {
  if (p >= 1_000_000) return `$${(p / 1_000_000).toFixed(2)}M`;
  if (p >= 1000) return `$${Math.round(p / 1000)}K`;
  return `$${p}`;
}

function formatRelative(iso: string): string {
  const d = daysSince(iso);
  if (d < 1) return "today";
  if (d < 7) return `${d}d ago`;
  if (d < 30) return `${Math.floor(d / 7)}w ago`;
  return new Date(iso).toLocaleDateString("en-AU", {
    day: "numeric",
    month: "short",
  });
}

/* ── Filter / sort options ─────────────────────────── */

type FilterKey = "all" | "position" | "price" | "team" | "recent" | "depth";
type SortKey = "name" | "recent" | "price" | "depth";

interface FilterOption {
  key: string;
  label: string;
  count: number;
  logo?: string | null;
}

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "position", label: "By position" },
  { key: "price", label: "By price" },
  { key: "team", label: "By team" },
  { key: "recent", label: "Recently spotted" },
  { key: "depth", label: "Knowledge depth" },
];

const SORTS: { key: SortKey; label: string }[] = [
  { key: "name", label: "Name (A–Z)" },
  { key: "recent", label: "Recently updated" },
  { key: "price", label: "Price (high → low)" },
  { key: "depth", label: "Knowledge depth" },
];

interface PriceBucket {
  key: string;
  label: string;
  min: number;
  max: number;
}

const PRICE_BUCKETS: PriceBucket[] = [
  { key: "u300", label: "Under $300K", min: 0, max: 300_000 },
  { key: "300-500", label: "$300K – $500K", min: 300_000, max: 500_000 },
  { key: "500-700", label: "$500K – $700K", min: 500_000, max: 700_000 },
  { key: "700-900", label: "$700K – $900K", min: 700_000, max: 900_000 },
  { key: "900-plus", label: "$900K+", min: 900_000, max: Number.POSITIVE_INFINITY },
];

function priceBucketFor(price: number | null): PriceBucket | null {
  if (price == null) return null;
  return PRICE_BUCKETS.find((b) => price >= b.min && price < b.max) ?? null;
}

// SuperCoach position codes are cryptic, and `CTW` covers both centres and
// wingers — wingers don't get their own filter chip. Map to friendly labels
// so the bundling is visible.
const POSITION_LABELS: Record<string, string> = {
  CTW: "Centre / Wing",
  FRF: "Front-row forward",
  "2RF": "Second-row forward",
  HOK: "Hooker",
  HFB: "Halfback",
  "5/8": "Five-eighth",
  FLB: "Fullback",
};

function positionLabel(code: string): string {
  return POSITION_LABELS[code] ?? code;
}


/* ── Stats derivation ─────────────────────────────── */

interface PlayerStats {
  total: number;
  withProfile: number;
  withTeam: number;
  recentlyUpdated: number;
  highConfidence: number;
}

function derivePlayerStats(pages: WikiPageSummary[]): PlayerStats {
  const total = pages.length;
  const withProfile = pages.filter((p) => p.summary).length;
  const withTeam = pages.filter((p) => getMetaString(p, "team")).length;
  const recentlyUpdated = pages.filter((p) => daysSince(p.updated_at) <= 7).length;
  const highConfidence = pages.filter((p) => p.status === "published").length;
  return { total, withProfile, withTeam, recentlyUpdated, highConfidence };
}

/* ══════════════════════════════════════════════════════
   PlayersIndexView — top-level players page
   ══════════════════════════════════════════════════════ */

export default function PlayersIndexView({
  pages,
}: {
  pages: WikiPageSummary[];
}) {
  const [activeFilter, setActiveFilter] = useState<FilterKey>("all");
  const [selectedTeams, setSelectedTeams] = useState<string[]>([]);
  const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
  const [selectedPriceBuckets, setSelectedPriceBuckets] = useState<string[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortOpen, setSortOpen] = useState(false);

  const stats = useMemo(() => derivePlayerStats(pages), [pages]);

  const teamOptions = useMemo<FilterOption[]>(() => {
    const map = new Map<string, FilterOption>();
    for (const p of pages) {
      const name = getMetaString(p, "team");
      if (!name) continue;
      const existing = map.get(name);
      if (existing) {
        existing.count += 1;
        if (!existing.logo) existing.logo = getMetaString(p, "team_logo");
      } else {
        map.set(name, {
          key: name,
          label: name,
          logo: getMetaString(p, "team_logo"),
          count: 1,
        });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [pages]);

  const positionOptions = useMemo<FilterOption[]>(() => {
    const map = new Map<string, FilterOption>();
    for (const p of pages) {
      const pos = getMetaString(p, "position");
      if (!pos) continue;
      const existing = map.get(pos);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(pos, { key: pos, label: positionLabel(pos), count: 1 });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [pages]);

  const priceOptions = useMemo<FilterOption[]>(() => {
    const counts = new Map<string, number>();
    for (const p of pages) {
      const bucket = priceBucketFor(getMetaNumber(p, "price"));
      if (!bucket) continue;
      counts.set(bucket.key, (counts.get(bucket.key) ?? 0) + 1);
    }
    return PRICE_BUCKETS.filter((b) => counts.has(b.key)).map((b) => ({
      key: b.key,
      label: b.label,
      count: counts.get(b.key) ?? 0,
    }));
  }, [pages]);

  const toggleInArray = (current: string[], key: string): string[] =>
    current.includes(key) ? current.filter((k) => k !== key) : [...current, key];

  const handleFilterSelect = (k: FilterKey) => {
    const isDrawerFilter = k === "team" || k === "position" || k === "price";
    if (isDrawerFilter && activeFilter === k) {
      setActiveFilter("all");
      setSelectedTeams([]);
      setSelectedPositions([]);
      setSelectedPriceBuckets([]);
      return;
    }
    setActiveFilter(k);
    setSelectedTeams([]);
    setSelectedPositions([]);
    setSelectedPriceBuckets([]);
  };

  const visible = useMemo(() => {
    let list = pages.slice();

    if (selectedTeams.length > 0) {
      list = list.filter((p) => {
        const t = getMetaString(p, "team");
        return t != null && selectedTeams.includes(t);
      });
    }

    if (selectedPositions.length > 0) {
      list = list.filter((p) => {
        const pos = getMetaString(p, "position");
        return pos != null && selectedPositions.includes(pos);
      });
    }

    if (selectedPriceBuckets.length > 0) {
      const buckets = PRICE_BUCKETS.filter((b) =>
        selectedPriceBuckets.includes(b.key),
      );
      list = list.filter((p) => {
        const price = getMetaNumber(p, "price");
        if (price == null) return false;
        return buckets.some((b) => price >= b.min && price < b.max);
      });
    }

    switch (sortKey) {
      case "recent":
        list.sort(
          (a, b) =>
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
        );
        break;
      case "price":
        list.sort(
          (a, b) =>
            (getMetaNumber(b, "price") ?? 0) - (getMetaNumber(a, "price") ?? 0),
        );
        break;
      case "depth":
        list.sort((a, b) => {
          const da = a.summary ? a.summary.length : 0;
          const dbb = b.summary ? b.summary.length : 0;
          return dbb - da;
        });
        break;
      default:
        list.sort((a, b) => a.title.localeCompare(b.title));
    }
    return list;
  }, [pages, selectedTeams, selectedPositions, selectedPriceBuckets, sortKey]);

  const lowEvidence = useMemo(() => {
    return pages
      .filter((p) => p.status !== "published" || !p.summary)
      .slice(0, 4);
  }, [pages]);

  return (
    <div className="wiki-page" data-theme="dark">
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

      <PageHeader />

      <KnowledgeStats stats={stats} />

      <KnowledgeHighlights pages={pages} />

      <AllPlayers
        pages={visible}
        total={visible.length}
        activeFilter={activeFilter}
        onFilterSelect={handleFilterSelect}
        teamOptions={teamOptions}
        selectedTeams={selectedTeams}
        onTeamToggle={(k) => setSelectedTeams((cur) => toggleInArray(cur, k))}
        onTeamClear={() => setSelectedTeams([])}
        positionOptions={positionOptions}
        selectedPositions={selectedPositions}
        onPositionToggle={(k) =>
          setSelectedPositions((cur) => toggleInArray(cur, k))
        }
        onPositionClear={() => setSelectedPositions([])}
        priceOptions={priceOptions}
        selectedPriceBuckets={selectedPriceBuckets}
        onPriceToggle={(k) =>
          setSelectedPriceBuckets((cur) => toggleInArray(cur, k))
        }
        onPriceClear={() => setSelectedPriceBuckets([])}
        sortKey={sortKey}
        sortOpen={sortOpen}
        onSortToggle={() => setSortOpen((o) => !o)}
        onSortPick={(k) => {
          setSortKey(k);
          setSortOpen(false);
        }}
      />

      {lowEvidence.length > 0 && <LowEvidence pages={lowEvidence} />}

      <AskAboutPlayer />
    </div>
  );
}

/* ── Page header ───────────────────────────────────── */

function PageHeader() {
  return (
    <header style={{ marginBottom: "2.5rem" }}>
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
        Players
      </h1>
      <p
        style={{
          fontFamily: v.serif,
          fontStyle: "italic",
          fontSize: "1.1rem",
          color: v.inkMuted,
          lineHeight: 1.5,
          maxWidth: 560,
        }}
      >
        Profile cards across positions, sources, and match context — every
        player Jaromelu has met on the page.
      </p>
    </header>
  );
}

/* ── Knowledge stats (5-card row) ─────────────────── */

function KnowledgeStats({ stats }: { stats: PlayerStats }) {
  const items: {
    icon: typeof Users;
    label: string;
    value: string;
    accent: string;
  }[] = [
    {
      icon: Users,
      label: "Players",
      value: String(stats.total),
      accent: v.accent,
    },
    {
      icon: Sparkles,
      label: "Profiled",
      value: String(stats.withProfile),
      accent: v.teal,
    },
    {
      icon: MapPin,
      label: "On a roster",
      value: String(stats.withTeam),
      accent: v.amber,
    },
    {
      icon: TrendingUp,
      label: "Updated this week",
      value: String(stats.recentlyUpdated),
      accent: v.purple,
    },
    {
      icon: CheckCircle2,
      label: "High confidence",
      value: String(stats.highConfidence),
      accent: v.green,
    },
  ];

  return (
    <section style={{ marginBottom: "2.75rem" }}>
      <SectionLabel>Jaromelu&rsquo;s player knowledge</SectionLabel>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "1px",
          background: v.border,
          border: `1px solid ${v.border}`,
          borderRadius: 6,
          overflow: "hidden",
          marginTop: "1rem",
        }}
      >
        {items.map(({ icon: Icon, label, value, accent }) => (
          <div
            key={label}
            style={{
              background: v.surface,
              padding: "1.2rem 1.1rem",
              display: "flex",
              flexDirection: "column",
              gap: "0.45rem",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.45rem",
                color: accent,
              }}
            >
              <Icon size={14} />
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 600,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: v.inkFaint,
                }}
              >
                {label}
              </span>
            </div>
            <div
              style={{
                fontFamily: v.serif,
                fontSize: "1.85rem",
                fontWeight: 700,
                color: v.ink,
                lineHeight: 1,
              }}
            >
              {value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ── Knowledge highlights (3 themed cards) ───────── */

function KnowledgeHighlights({ pages }: { pages: WikiPageSummary[] }) {
  const recent = useMemo(
    () =>
      pages
        .slice()
        .sort(
          (a, b) =>
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
        )[0],
    [pages],
  );

  const updatedThisWeek = pages.filter(
    (p) => daysSince(p.updated_at) <= 7,
  ).length;
  const stubCount = pages.filter((p) => p.status === "stub").length;

  return (
    <section style={{ marginBottom: "2.75rem" }}>
      <SectionLabel>What Jaromelu knows right now</SectionLabel>
      <div
        className="grid grid-cols-1 md:grid-cols-3"
        style={{ gap: "1rem", marginTop: "1rem" }}
      >
        <HighlightCard
          tone="accent"
          eyebrow="Featured player"
          title={
            recent
              ? `${recent.title}’s page is moving.`
              : "No featured player yet."
          }
          body={
            recent?.summary ??
            "When the agent rewrites a player section, the freshest one surfaces here."
          }
          rightSlot={<RingScore value={recent ? 76 : 0} />}
          href={recent ? pageHref(recent) : undefined}
          ctaLabel="Open page"
        />
        <HighlightCard
          tone="teal"
          eyebrow="Activity this week"
          title="Spine control is deciding tight games."
          body="Halves and hookers move the needle most when knowledge updates land. Recent edits keep stacking around the playmakers."
          bigNumber={updatedThisWeek}
          bigSuffix="updates"
          ctaLabel="Browse recently spotted"
        />
        <HighlightCard
          tone="amber"
          eyebrow="Open ground"
          title="Young playmakers are stepping in."
          body="Stubs Jaromelu has met but hasn’t yet written up — fresh signals are the fastest way to close the gap."
          bigNumber={stubCount}
          bigSuffix="stubs"
          ctaLabel="See low-evidence list"
        />
      </div>
    </section>
  );
}

function HighlightCard({
  tone,
  eyebrow,
  title,
  body,
  rightSlot,
  bigNumber,
  bigSuffix,
  href,
  ctaLabel,
}: {
  tone: "accent" | "teal" | "amber";
  eyebrow: string;
  title: string;
  body: string;
  rightSlot?: React.ReactNode;
  bigNumber?: number;
  bigSuffix?: string;
  href?: string;
  ctaLabel: string;
}) {
  const palette = {
    accent: { fg: v.accent, bg: v.accentBg },
    teal: { fg: v.teal, bg: v.tealBg },
    amber: { fg: v.amber, bg: v.amberBg },
  }[tone];

  const Inner = (
    <>
      <div
        style={{
          fontSize: "11px",
          fontWeight: 600,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: palette.fg,
          marginBottom: "0.65rem",
        }}
      >
        {eyebrow}
      </div>
      <div
        className="flex items-start"
        style={{ gap: "0.85rem", marginBottom: "0.75rem" }}
      >
        <h3
          style={{
            fontFamily: v.serif,
            fontSize: "1.15rem",
            fontWeight: 700,
            color: v.ink,
            lineHeight: 1.25,
            flex: 1,
          }}
        >
          {title}
        </h3>
        {rightSlot}
        {bigNumber !== undefined && (
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div
              style={{
                fontFamily: v.serif,
                fontSize: "2.1rem",
                fontWeight: 700,
                color: palette.fg,
                lineHeight: 1,
              }}
            >
              {bigNumber}
            </div>
            {bigSuffix && (
              <div
                style={{
                  fontSize: "10px",
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color: v.inkFaint,
                  marginTop: "0.25rem",
                }}
              >
                {bigSuffix}
              </div>
            )}
          </div>
        )}
      </div>
      <p
        style={{
          fontSize: "13px",
          color: v.inkMuted,
          lineHeight: 1.55,
          marginBottom: "0.85rem",
        }}
      >
        {body}
      </p>
      <div
        style={{
          fontSize: "12px",
          fontWeight: 600,
          color: palette.fg,
          display: "inline-flex",
          alignItems: "center",
          gap: "0.3rem",
        }}
      >
        {ctaLabel} <ArrowRight size={12} />
      </div>
    </>
  );

  const cardStyle: React.CSSProperties = {
    background: palette.bg,
    border: `1px solid ${palette.fg}`,
    borderRadius: 6,
    padding: "1.4rem 1.3rem",
    display: "block",
    textDecoration: "none",
    color: "inherit",
  };

  if (href) {
    return (
      <Link href={href} style={cardStyle}>
        {Inner}
      </Link>
    );
  }
  return <div style={cardStyle}>{Inner}</div>;
}

function RingScore({ value }: { value: number }) {
  const r = 22;
  const c = 2 * Math.PI * r;
  const dash = (value / 100) * c;
  return (
    <div style={{ flexShrink: 0, position: "relative", width: 56, height: 56 }}>
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle
          cx="28"
          cy="28"
          r={r}
          stroke="var(--wiki-border)"
          strokeWidth="4"
          fill="none"
        />
        <circle
          cx="28"
          cy="28"
          r={r}
          stroke="var(--wiki-accent)"
          strokeWidth="4"
          fill="none"
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          transform="rotate(-90 28 28)"
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: v.serif,
          fontSize: "0.95rem",
          fontWeight: 700,
          color: v.ink,
        }}
      >
        {value}
      </div>
    </div>
  );
}

/* ── All players grid ───────────────────────────── */

function AllPlayers({
  pages,
  total,
  activeFilter,
  onFilterSelect,
  teamOptions,
  selectedTeams,
  onTeamToggle,
  onTeamClear,
  positionOptions,
  selectedPositions,
  onPositionToggle,
  onPositionClear,
  priceOptions,
  selectedPriceBuckets,
  onPriceToggle,
  onPriceClear,
  sortKey,
  sortOpen,
  onSortToggle,
  onSortPick,
}: {
  pages: WikiPageSummary[];
  total: number;
  activeFilter: FilterKey;
  onFilterSelect: (k: FilterKey) => void;
  teamOptions: FilterOption[];
  selectedTeams: string[];
  onTeamToggle: (k: string) => void;
  onTeamClear: () => void;
  positionOptions: FilterOption[];
  selectedPositions: string[];
  onPositionToggle: (k: string) => void;
  onPositionClear: () => void;
  priceOptions: FilterOption[];
  selectedPriceBuckets: string[];
  onPriceToggle: (k: string) => void;
  onPriceClear: () => void;
  sortKey: SortKey;
  sortOpen: boolean;
  onSortToggle: () => void;
  onSortPick: (k: SortKey) => void;
}) {
  return (
    <section style={{ marginBottom: "2.75rem" }}>
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
          All players{" "}
          <span
            style={{
              fontSize: "13px",
              fontWeight: 400,
              color: v.inkFaint,
              marginLeft: "0.4rem",
            }}
          >
            ({total})
          </span>
        </h2>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            flexWrap: "wrap",
          }}
        >
          {FILTERS.map((f) => {
            const isActive = activeFilter === f.key;
            return (
              <button
                key={f.key}
                onClick={() => onFilterSelect(f.key)}
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  padding: "0.4rem 0.85rem",
                  borderRadius: 999,
                  border: `1px solid ${isActive ? v.accent : v.border}`,
                  background: isActive ? v.accentBg : v.surface,
                  color: isActive ? v.accent : v.inkMuted,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "background 0.15s, color 0.15s, border-color 0.15s",
                }}
              >
                {f.label}
              </button>
            );
          })}
          <div style={{ position: "relative" }}>
          <button
            onClick={onSortToggle}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.4rem",
              padding: "0.4rem 0.85rem",
              fontSize: "12px",
              fontWeight: 600,
              color: v.inkMuted,
              background: v.surface,
              border: `1px solid ${v.border}`,
              borderRadius: 6,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Sort: {SORTS.find((s) => s.key === sortKey)?.label}
            <ChevronDown size={12} />
          </button>
          {sortOpen && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                right: 0,
                background: v.surface,
                border: `1px solid ${v.border}`,
                borderRadius: 6,
                padding: "0.35rem",
                minWidth: 180,
                zIndex: 5,
                boxShadow: "0 6px 20px rgba(0,0,0,0.25)",
              }}
            >
              {SORTS.map((s) => (
                <button
                  key={s.key}
                  onClick={() => onSortPick(s.key)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    padding: "0.45rem 0.7rem",
                    fontSize: "12px",
                    background:
                      s.key === sortKey ? v.accentBg : "transparent",
                    color: s.key === sortKey ? v.accent : v.ink,
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    borderRadius: 4,
                  }}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
          </div>
        </div>
      </div>

      {activeFilter === "team" && (
        <FilterDrawer
          title="Filter by team"
          searchable
          searchPlaceholder="Search teams…"
          options={teamOptions}
          selectedKeys={selectedTeams}
          onToggle={onTeamToggle}
          onClear={onTeamClear}
          allLabel="All teams"
          allIcon={<Users size={13} />}
        />
      )}
      {activeFilter === "position" && (
        <FilterDrawer
          title="Filter by position"
          options={positionOptions}
          selectedKeys={selectedPositions}
          onToggle={onPositionToggle}
          onClear={onPositionClear}
          allLabel="All positions"
          allIcon={<MapPin size={13} />}
        />
      )}
      {activeFilter === "price" && (
        <FilterDrawer
          title="Filter by price"
          options={priceOptions}
          selectedKeys={selectedPriceBuckets}
          onToggle={onPriceToggle}
          onClear={onPriceClear}
          allLabel="All prices"
          allIcon={<DollarSign size={13} />}
        />
      )}

      {pages.length === 0 ? (
        <EmptyPlayers />
      ) : (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
          style={{ gap: "1rem" }}
        >
          {pages.map((p) => (
            <PlayerCard key={p.page_id} page={p} />
          ))}
        </div>
      )}
    </section>
  );
}

function PlayerCard({ page }: { page: WikiPageSummary }) {
  const team = getMetaString(page, "team");
  const position = getMetaString(page, "position");
  const price = getMetaNumber(page, "price");
  const sourceCount = getMetaNumber(page, "source_count");
  const claimCount = getMetaNumber(page, "claim_count");
  const updated = formatRelative(page.updated_at);

  return (
    <Link
      href={pageHref(page)}
      style={{
        display: "flex",
        gap: "1.1rem",
        background: v.surface,
        border: `1px solid ${v.border}`,
        borderRadius: 8,
        padding: "1.1rem",
        color: "inherit",
        textDecoration: "none",
        transition: "border-color 0.15s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = v.accent;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--wiki-border)";
      }}
    >
      <div style={{ flexShrink: 0 }}>
        {page.logo_url ? (
          <img
            src={page.logo_url}
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
            {initials(page.title)}
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
          {page.title}
        </h3>
        {(position || team) && (
          <div
            style={{
              fontSize: "12px",
              color: v.inkFaint,
              marginBottom: "0.45rem",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {position ? <span style={{ color: v.amber }}>{position}</span> : null}
            {position && team ? " · " : null}
            {team ?? (position ? null : "Unaffiliated")}
          </div>
        )}
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
          {page.summary || "No summary yet."}
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
          {price != null && (
            <span
              title="Price"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
                color: v.green,
              }}
            >
              <DollarSign size={11} /> {formatPrice(price)}
            </span>
          )}
          {sourceCount != null && (
            <span
              title="Voices on file"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <Mic size={11} /> {sourceCount}
            </span>
          )}
          {claimCount != null && (
            <span
              title="Claims about this player"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <Activity size={11} /> {claimCount}
            </span>
          )}
          {updated && (
            <span
              style={{
                marginLeft: "auto",
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
    </Link>
  );
}

function Avatar({
  logoUrl,
  title,
}: {
  logoUrl: string | null | undefined;
  title: string;
}) {
  return (
    <div
      style={{
        width: 44,
        height: 44,
        borderRadius: "50%",
        background: v.accentBg,
        color: v.accent,
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "12px",
        fontWeight: 700,
        letterSpacing: "0.04em",
        border: `1px solid ${v.border}`,
        overflow: "hidden",
      }}
    >
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt=""
          width={44}
          height={44}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          loading="lazy"
          referrerPolicy="no-referrer"
        />
      ) : (
        initials(title)
      )}
    </div>
  );
}

function EmptyPlayers() {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "3rem 1rem",
        background: v.surface,
        border: `1px dashed ${v.border}`,
        borderRadius: 6,
      }}
    >
      <Users
        size={28}
        style={{ color: v.inkFaint, marginBottom: "0.6rem", opacity: 0.5 }}
      />
      <div
        style={{
          fontFamily: v.serif,
          fontSize: "1.1rem",
          fontWeight: 700,
          color: v.ink,
          marginBottom: "0.3rem",
        }}
      >
        No player pages yet.
      </div>
      <p style={{ fontSize: "13px", color: v.inkFaint, margin: 0 }}>
        Jaromelu hasn&rsquo;t written up any players yet. Pages will appear
        here as the crew enriches them.
      </p>
    </div>
  );
}

/* ── Players that need more evidence ────────────── */

function LowEvidence({ pages }: { pages: WikiPageSummary[] }) {
  return (
    <section style={{ marginBottom: "2.75rem" }}>
      <SectionLabel>Players that need more evidence</SectionLabel>
      <p
        style={{
          fontSize: "13px",
          color: v.inkMuted,
          marginTop: "0.4rem",
          marginBottom: "1rem",
          maxWidth: 540,
        }}
      >
        Stubs and drafts where Jaromelu has the player on record but is still
        looking for sources.
      </p>
      <div
        className="grid grid-cols-2 lg:grid-cols-4"
        style={{ gap: "0.75rem" }}
      >
        {pages.map((p) => {
          const team = getMetaString(p, "team");
          const position = getMetaString(p, "position");
          return (
            <Link
              key={p.page_id}
              href={pageHref(p)}
              className="group"
              style={{
                display: "flex",
                gap: "0.7rem",
                alignItems: "center",
                padding: "0.85rem",
                background: v.surface,
                border: `1px solid ${v.border}`,
                borderRadius: 6,
                textDecoration: "none",
                color: "inherit",
              }}
            >
              <Avatar logoUrl={p.logo_url} title={p.title} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  className="group-hover:underline"
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: v.ink,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {p.title}
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
                  {position ? `${position} · ` : ""}
                  {team ?? p.status}
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

/* ── Ask about a player ─────────────────────────── */

const ASK_PROMPTS = [
  "Why is Reece Walsh dropping?",
  "Compare Cleary and DCE this season.",
  "Which spine players are trending up?",
  "Cheap rookies starting next round.",
  "Players returning from injury.",
];

function AskAboutPlayer() {
  const [question, setQuestion] = useState("");
  const [chipOffset, setChipOffset] = useState(0);

  const chips = useMemo(() => {
    const start = chipOffset % ASK_PROMPTS.length;
    return [...ASK_PROMPTS.slice(start), ...ASK_PROMPTS.slice(0, start)].slice(
      0,
      3,
    );
  }, [chipOffset]);

  return (
    <section
      style={{
        padding: "1.75rem 0 0.5rem",
        borderTop: `1px solid ${v.border}`,
        marginBottom: "2rem",
      }}
    >
      <SectionLabel>Ask about a player</SectionLabel>
      <h2
        style={{
          fontFamily: v.serif,
          fontSize: "1.4rem",
          fontWeight: 700,
          color: v.ink,
          marginTop: "0.3rem",
          marginBottom: "1rem",
        }}
      >
        Need a quick read on someone?
      </h2>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          alignItems: "center",
          marginBottom: "0.85rem",
        }}
      >
        {chips.map((c) => (
          <span
            key={c}
            style={{
              fontSize: "12px",
              padding: "0.4rem 0.8rem",
              borderRadius: 999,
              border: `1px solid ${v.border}`,
              background: v.surface,
              color: v.inkMuted,
            }}
          >
            {c}
          </span>
        ))}
        <button
          onClick={() => setChipOffset((o) => o + 3)}
          aria-label="Refresh prompts"
          style={{
            width: 28,
            height: 28,
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
          <RefreshCw size={12} />
        </button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!question.trim()) return;
          const params = new URLSearchParams({ q: question.trim() });
          window.location.href = `/ask?${params.toString()}`;
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
          placeholder="Ask about a specific player…"
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
    </section>
  );
}

/* ── Filter drawer (team / position / price) ──── */

function FilterDrawer({
  title,
  options,
  selectedKeys,
  onToggle,
  onClear,
  allLabel,
  allIcon,
  searchable,
  searchPlaceholder,
}: {
  title: string;
  options: FilterOption[];
  selectedKeys: string[];
  onToggle: (key: string) => void;
  onClear: () => void;
  allLabel: string;
  allIcon: React.ReactNode;
  searchable?: boolean;
  searchPlaceholder?: string;
}) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!searchable) return options;
    const q = search.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, search, searchable]);

  const selectedOptions =
    selectedKeys.length === 0
      ? []
      : selectedKeys
          .map((k) => options.find((o) => o.key === k))
          .filter((o): o is FilterOption => o != null);

  return (
    <div
      style={{
        marginBottom: "1rem",
        padding: "1rem 1.1rem",
        background: v.surface,
        border: `1px solid ${v.border}`,
        borderRadius: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.85rem",
          flexWrap: "wrap",
          marginBottom: "0.85rem",
        }}
      >
        <span
          style={{
            fontSize: "11px",
            fontWeight: 600,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: v.inkFaint,
          }}
        >
          {title}
        </span>
        {searchable && (
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.4rem",
              background: v.bg,
              border: `1px solid ${v.border}`,
              borderRadius: 6,
              padding: "0.3rem 0.65rem",
              flex: 1,
              maxWidth: 240,
              minWidth: 180,
            }}
          >
            <Search size={12} style={{ color: v.inkFaint }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={searchPlaceholder ?? "Search…"}
              style={{
                border: "none",
                background: "transparent",
                outline: "none",
                fontSize: "12px",
                color: v.ink,
                fontFamily: "inherit",
                flex: 1,
                minWidth: 0,
              }}
            />
          </label>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.4rem",
        }}
      >
        <FilterDrawerChip
          active={selectedKeys.length === 0}
          onClick={onClear}
          label={allLabel}
          icon={allIcon}
        />
        {filtered.map((o) => (
          <FilterDrawerChip
            key={o.key}
            active={selectedKeys.includes(o.key)}
            onClick={() => onToggle(o.key)}
            label={o.label}
            count={o.count}
            logo={o.logo}
          />
        ))}
        {filtered.length === 0 && (
          <span
            style={{
              fontSize: "12px",
              color: v.inkFaint,
              padding: "0.4rem 0.2rem",
            }}
          >
            No matches.
          </span>
        )}
      </div>

      {selectedOptions.length > 0 && (
        <div
          style={{
            marginTop: "0.85rem",
            paddingTop: "0.85rem",
            borderTop: `1px solid ${v.border}`,
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            flexWrap: "wrap",
            fontSize: "12px",
            color: v.inkFaint,
          }}
        >
          <span style={{ fontWeight: 600 }}>Showing:</span>
          {selectedOptions.map((o) => (
            <button
              key={o.key}
              type="button"
              onClick={() => onToggle(o.key)}
              aria-label={`Remove ${o.label} from filter`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
                padding: "0.25rem 0.6rem",
                borderRadius: 999,
                border: `1px solid ${v.accent}`,
                background: v.accentBg,
                color: v.accent,
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {o.label}
              <X size={11} />
            </button>
          ))}
          {selectedOptions.length > 1 && (
            <button
              type="button"
              onClick={onClear}
              style={{
                fontSize: "11px",
                fontWeight: 600,
                color: v.inkFaint,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontFamily: "inherit",
                textDecoration: "underline",
                padding: 0,
              }}
            >
              Clear all
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function FilterDrawerChip({
  active,
  onClick,
  label,
  count,
  logo,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
  logo?: string | null;
  icon?: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.45rem",
        padding: "0.35rem 0.7rem 0.35rem 0.45rem",
        borderRadius: 999,
        border: `1px solid ${active ? v.accent : v.border}`,
        background: active ? v.accentBg : v.bg,
        color: active ? v.accent : v.inkMuted,
        fontSize: "12px",
        fontWeight: 600,
        cursor: "pointer",
        fontFamily: "inherit",
        transition: "background 0.15s, color 0.15s, border-color 0.15s",
      }}
    >
      {logo ? (
        <img
          src={logo}
          alt=""
          width={20}
          height={20}
          style={{
            width: 20,
            height: 20,
            borderRadius: 4,
            objectFit: "contain",
            background: "rgba(255,255,255,0.04)",
            flexShrink: 0,
          }}
          loading="lazy"
          referrerPolicy="no-referrer"
        />
      ) : icon ? (
        <span
          style={{
            width: 20,
            height: 20,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 4,
            background: active ? "rgba(255,255,255,0.04)" : v.surface,
            color: active ? v.accent : v.inkFaint,
            flexShrink: 0,
          }}
        >
          {icon}
        </span>
      ) : null}
      <span>{label}</span>
      {count != null && (
        <span
          style={{
            fontSize: "11px",
            fontWeight: 700,
            color: active ? v.accent : v.inkFaint,
            marginLeft: "0.15rem",
          }}
        >
          {count}
        </span>
      )}
    </button>
  );
}

/* ── Section primitives ─────────────────────────── */

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: v.accent,
      }}
    >
      {children}
    </div>
  );
}
