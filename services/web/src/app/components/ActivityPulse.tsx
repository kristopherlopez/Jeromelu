"use client";

import { useEffect, useState } from "react";

interface Stats {
  sources_scanned: number;
  claims_extracted: number;
  latest_source: {
    title: string;
    creator_name: string | null;
    ingested_at: string | null;
  } | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL!;

export function ActivityPulse() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/stats`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setStats)
      .catch(() => {});
  }, []);

  if (!stats || stats.sources_scanned === 0) return null;

  const parts: string[] = [];
  if (stats.sources_scanned > 0) {
    parts.push(`${stats.sources_scanned} sources scanned`);
  }
  if (stats.claims_extracted > 0) {
    parts.push(`${stats.claims_extracted} claims extracted`);
  }

  return (
    <p className="text-xs text-zinc-600 font-mono tracking-wide">
      {parts.join(" · ")}
    </p>
  );
}
