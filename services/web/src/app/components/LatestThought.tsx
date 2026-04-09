"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

// TODO: Replace with real Feed item type once the Feed exists
interface LatestThoughtData {
  text: string;
  timestamp: string;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function LatestThought() {
  // TODO: Fetch from /api/feed/latest once the Feed pipeline is built.
  // Until then, this component renders nothing — no fake data.
  const [thought] = useState<LatestThoughtData | null>(null);

  if (!thought) return null;

  return (
    <Link
      href="/"
      className="group max-w-md rounded-lg border border-zinc-800/60 bg-zinc-950 px-5 py-4 text-left transition-colors hover:border-zinc-700"
    >
      <p className="text-sm leading-relaxed text-zinc-300 group-hover:text-zinc-100 italic">
        &ldquo;{thought.text}&rdquo;
      </p>
      <p className="mt-2 text-xs text-zinc-600">
        {timeAgo(thought.timestamp)}
      </p>
    </Link>
  );
}
