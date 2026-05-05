"use client";

import { useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";
import type { PersonSummary } from "@/lib/types";

interface Props {
  onSelect: (person: PersonSummary) => void;
  placeholder?: string;
  autoFocus?: boolean;
}

const DEBOUNCE_MS = 150;

export default function PersonPicker({ onSelect, placeholder = "Search hosts and players…", autoFocus }: Props) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PersonSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  // Debounced fetch on query change. Cancellation flag lives in the outer
  // effect scope so the useEffect cleanup can flip it — earlier the flag
  // was scoped inside the setTimeout callback and never reached the inflight
  // fetch, letting stale results overwrite newer ones on fast typing.
  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(() => {
      setLoading(true);
      setError(null);
      fetch(`${API_BASE}/api/people/search?q=${encodeURIComponent(query)}&limit=30`)
        .then((r) => {
          if (!r.ok) throw new Error(`API ${r.status}`);
          return r.json();
        })
        .then((j: { items: PersonSummary[] }) => {
          if (!cancelled) setItems(j.items);
        })
        .catch((e: unknown) => {
          if (!cancelled) setError(String(e));
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [query]);

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded border px-3 py-2 text-sm"
        style={{
          borderColor: "var(--border)",
          backgroundColor: "var(--background-deep)",
          color: "var(--foreground)",
        }}
      />
      {loading && (
        <p className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
          searching…
        </p>
      )}
      {error && (
        <p className="text-xs text-red-400">error: {error}</p>
      )}
      <ul
        className="flex max-h-72 flex-col gap-px overflow-y-auto rounded border"
        style={{ borderColor: "var(--border)" }}
      >
        {items.length === 0 && !loading && (
          <li className="px-3 py-2 text-xs" style={{ color: "var(--foreground-ghost)" }}>
            no matches
          </li>
        )}
        {items.map((p) => (
          <li key={p.person_id}>
            <button
              type="button"
              onClick={() => onSelect(p)}
              className="flex w-full items-baseline justify-between px-3 py-2 text-left text-sm transition-colors hover:bg-white/5"
              style={{ color: "var(--foreground)" }}
            >
              <span>{p.canonical_name}</span>
              {p.slug && (
                <span
                  className="ml-2 truncate text-[11px]"
                  style={{ color: "var(--foreground-ghost)" }}
                >
                  {p.slug}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
