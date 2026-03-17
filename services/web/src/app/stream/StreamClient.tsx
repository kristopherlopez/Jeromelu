"use client";

import Link from "next/link";
import { useState, useMemo, useRef } from "react";
import type { SourceListItem } from "@/lib/types";

type SortKey = "newest" | "oldest" | "most_claims" | "alphabetical";
type GroupMode = "none" | "creator" | "date";

const PAGE_SIZE = 30;

function getDateGroup(dateStr: string | null): string {
  if (!dateStr) return "Unknown date";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 7) return "This week";
  if (diffDays < 14) return "Last week";
  return d.toLocaleDateString("en-AU", { month: "long", year: "numeric" });
}

function getShortDate(dateStr: string | null): string {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString("en-AU", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function isSameDay(a: string | null, b: string | null): boolean {
  if (!a || !b) return false;
  return new Date(a).toDateString() === new Date(b).toDateString();
}

function sortSources(items: SourceListItem[], sortKey: SortKey): SourceListItem[] {
  const sorted = [...items];
  switch (sortKey) {
    case "newest":
      return sorted.sort((a, b) => {
        if (!a.published_at) return 1;
        if (!b.published_at) return -1;
        return new Date(b.published_at).getTime() - new Date(a.published_at).getTime();
      });
    case "oldest":
      return sorted.sort((a, b) => {
        if (!a.published_at) return 1;
        if (!b.published_at) return -1;
        return new Date(a.published_at).getTime() - new Date(b.published_at).getTime();
      });
    case "most_claims":
      return sorted.sort((a, b) => b.claim_count - a.claim_count);
    case "alphabetical":
      return sorted.sort((a, b) => a.title.localeCompare(b.title));
    default:
      return sorted;
  }
}

interface GroupedSources {
  label: string;
  count: number;
  totalClaims: number;
  items: SourceListItem[];
}

function groupSources(
  items: SourceListItem[],
  mode: GroupMode
): GroupedSources[] {
  if (mode === "none") {
    return [{ label: "", count: items.length, totalClaims: 0, items }];
  }

  const map = new Map<string, SourceListItem[]>();
  for (const item of items) {
    const key =
      mode === "creator"
        ? item.creator_name || "Unknown creator"
        : getDateGroup(item.published_at);
    const list = map.get(key) || [];
    list.push(item);
    map.set(key, list);
  }

  const groups: GroupedSources[] = [];
  for (const [label, groupItems] of map) {
    groups.push({
      label,
      count: groupItems.length,
      totalClaims: groupItems.reduce((sum, s) => sum + s.claim_count, 0),
      items: groupItems,
    });
  }

  if (mode === "creator") {
    groups.sort((a, b) => b.count - a.count);
  }

  return groups;
}

function SourceRow({ source }: { source: SourceListItem }) {
  const hasClaims = source.claim_count > 0;

  return (
    <Link
      href={`/stream/${source.source_id}`}
      className="group flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-zinc-800/80 rounded-md"
    >
      {/* Claim count badge */}
      <div
        className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-xs font-semibold"
        style={
          hasClaims
            ? { backgroundColor: "rgba(245, 130, 32, 0.15)", color: "var(--tigers-orange)" }
            : { backgroundColor: "rgba(255,255,255,0.04)", color: "rgb(82,82,91)" }
        }
      >
        {source.claim_count}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <h2 className="text-sm text-zinc-300 group-hover:text-white line-clamp-1 leading-snug">
          {source.title}
        </h2>
        {source.creator_name && (
          <p className="mt-0.5 text-xs text-zinc-600 truncate">
            {source.creator_name}
          </p>
        )}
      </div>

      {/* Arrow */}
      <svg
        className="h-3.5 w-3.5 flex-shrink-0 text-zinc-800 group-hover:text-zinc-400 transition-colors"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </Link>
  );
}

function DateHeader({ date }: { date: string }) {
  return (
    <div className="flex items-center gap-3 px-3 pt-5 pb-1.5 first:pt-0">
      <span className="text-xs font-medium text-zinc-500">{date}</span>
      <div className="flex-1 border-t border-zinc-800/50" />
    </div>
  );
}

function SourceListWithDateHeaders({
  items,
  showDateHeaders,
}: {
  items: SourceListItem[];
  showDateHeaders: boolean;
}) {
  if (!showDateHeaders) {
    return (
      <div className="divide-y divide-zinc-800/40">
        {items.map((source) => (
          <SourceRow key={source.source_id} source={source} />
        ))}
      </div>
    );
  }

  const elements: React.ReactNode[] = [];
  let lastDate: string | null = null;

  for (const source of items) {
    if (!isSameDay(source.published_at, lastDate)) {
      const dateLabel = getShortDate(source.published_at) || "Unknown date";
      elements.push(<DateHeader key={`date-${dateLabel}`} date={dateLabel} />);
      lastDate = source.published_at;
    }
    elements.push(<SourceRow key={source.source_id} source={source} />);
  }

  return <div>{elements}</div>;
}

function CollapsibleGroup({
  group,
  defaultOpen,
}: {
  group: GroupedSources;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="mb-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left rounded-md hover:bg-zinc-800/40 transition-colors"
      >
        <svg
          className={`h-3 w-3 text-zinc-600 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-sm font-medium text-zinc-300">
          {group.label}
        </span>
        <span className="text-xs text-zinc-600">
          {group.count}
        </span>
        {group.totalClaims > 0 && (
          <span
            className="text-xs"
            style={{ color: "var(--tigers-orange)", opacity: 0.7 }}
          >
            {group.totalClaims} claims
          </span>
        )}
      </button>
      {open && (
        <div className="ml-2 border-l border-zinc-800/60 pl-1">
          <div className="divide-y divide-zinc-800/40">
            {group.items.map((source) => (
              <SourceRow key={source.source_id} source={source} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CreatorDropdown({
  creators,
  selected,
  onSelect,
}: {
  creators: [string, number][];
  selected: string | null;
  onSelect: (name: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
          selected
            ? "border-orange-800/50 bg-orange-950/30 text-orange-300"
            : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-600"
        }`}
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        {selected || "All creators"}
        {selected && (
          <span
            onClick={(e) => {
              e.stopPropagation();
              onSelect(null);
              setOpen(false);
            }}
            className="ml-0.5 hover:text-white"
          >
            ×
          </span>
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-20 mt-1 w-64 rounded-lg border border-zinc-700 bg-zinc-900 py-1 shadow-xl">
            <button
              onClick={() => { onSelect(null); setOpen(false); }}
              className={`flex w-full items-center justify-between px-3 py-1.5 text-xs hover:bg-zinc-800 ${
                !selected ? "text-white" : "text-zinc-400"
              }`}
            >
              All creators
              {!selected && <CheckIcon />}
            </button>
            <div className="mx-2 my-1 border-t border-zinc-800" />
            {creators.map(([name, count]) => (
              <button
                key={name}
                onClick={() => { onSelect(selected === name ? null : name); setOpen(false); }}
                className={`flex w-full items-center justify-between px-3 py-1.5 text-xs hover:bg-zinc-800 ${
                  selected === name ? "text-white" : "text-zinc-400"
                }`}
              >
                <span className="truncate">{name}</span>
                <span className="ml-2 flex items-center gap-1.5">
                  <span className="text-zinc-600">{count}</span>
                  {selected === name && <CheckIcon />}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function CheckIcon() {
  return (
    <svg className="h-3.5 w-3.5" style={{ color: "var(--tigers-orange)" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

export default function StreamClient({ sources }: { sources: SourceListItem[] }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("newest");
  const [groupBy, setGroupBy] = useState<GroupMode>("none");
  const [creatorFilter, setCreatorFilter] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const creators = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of sources) {
      const name = s.creator_name || "Unknown";
      counts.set(name, (counts.get(name) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [sources]);

  const filtered = useMemo(() => {
    let items = sources;
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(
        (s) =>
          s.title.toLowerCase().includes(q) ||
          (s.creator_name && s.creator_name.toLowerCase().includes(q))
      );
    }
    if (creatorFilter) {
      items = items.filter(
        (s) => (s.creator_name || "Unknown") === creatorFilter
      );
    }
    return items;
  }, [sources, search, creatorFilter]);

  const sorted = useMemo(() => sortSources(filtered, sort), [filtered, sort]);
  const groups = useMemo(() => groupSources(sorted, groupBy), [sorted, groupBy]);

  const paginatedGroups = useMemo(() => {
    if (groupBy !== "none") return groups;
    return groups.map((g) => ({
      ...g,
      items: g.items.slice(0, visibleCount),
    }));
  }, [groups, groupBy, visibleCount]);

  const totalFiltered = filtered.length;
  const hasMore = groupBy === "none" && visibleCount < totalFiltered;

  // Show inline date headers when sorted by date and not grouped
  const showDateHeaders = groupBy === "none" && (sort === "newest" || sort === "oldest");

  return (
    <div className="mx-auto max-w-4xl">
      {/* Toolbar */}
      <div className="mb-5 space-y-3">
        {/* Search */}
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search by title or creator..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setVisibleCount(PAGE_SIZE);
            }}
            className="w-full rounded-md border border-zinc-800 bg-zinc-900/50 py-2 pl-10 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-600 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Controls row */}
        <div className="flex items-center gap-2">
          <CreatorDropdown
            creators={creators}
            selected={creatorFilter}
            onSelect={(name) => { setCreatorFilter(name); setVisibleCount(PAGE_SIZE); }}
          />

          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-zinc-400 outline-none focus:border-zinc-600"
          >
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="most_claims">Most claims</option>
            <option value="alphabetical">A–Z</option>
          </select>

          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as GroupMode)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-zinc-400 outline-none focus:border-zinc-600"
          >
            <option value="none">No grouping</option>
            <option value="creator">Group by creator</option>
            <option value="date">Group by date</option>
          </select>

          <span className="ml-auto text-xs text-zinc-600">
            {totalFiltered === sources.length
              ? `${totalFiltered} sources`
              : `${totalFiltered} of ${sources.length}`}
          </span>
        </div>
      </div>

      {/* Results */}
      {totalFiltered === 0 ? (
        <p className="text-center text-zinc-600 py-16 text-sm">
          No sources match your filters.
        </p>
      ) : groupBy !== "none" ? (
        paginatedGroups.map((group) => (
          <CollapsibleGroup
            key={group.label}
            group={group}
            defaultOpen={paginatedGroups.length <= 5 || group.items.length <= 6}
          />
        ))
      ) : (
        <>
          <SourceListWithDateHeaders
            items={paginatedGroups[0]?.items ?? []}
            showDateHeaders={showDateHeaders}
          />
          {hasMore && (
            <div className="mt-4 text-center">
              <button
                onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
                className="rounded-md px-5 py-1.5 text-xs text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition-colors"
              >
                Show more · {totalFiltered - visibleCount} remaining
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
