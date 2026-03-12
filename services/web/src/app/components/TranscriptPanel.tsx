"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { TranscriptChunk } from "@/lib/types";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  chunks: TranscriptChunk[];
  currentTime: number;
  onSeek: (seconds: number) => void;
}

export default function TranscriptPanel({ chunks, currentTime, onSeek }: Props) {
  const [open, setOpen] = useState(false);

  const activeChunkId = chunks.find(
    (ch) =>
      ch.start_ts !== null &&
      ch.end_ts !== null &&
      currentTime >= ch.start_ts &&
      currentTime < ch.end_ts
  )?.chunk_id;

  return (
    <div className="rounded-lg border border-zinc-800">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium text-zinc-300 cursor-pointer hover:bg-zinc-900 transition-colors"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        Transcript ({chunks.length} chunks)
      </button>

      {open && (
        <div className="max-h-96 overflow-y-auto border-t border-zinc-800 px-4 py-3">
          <div className="space-y-1">
            {chunks.map((chunk) => {
              const isActive = chunk.chunk_id === activeChunkId;
              return (
                <span
                  key={chunk.chunk_id}
                  onClick={() => chunk.start_ts !== null && onSeek(chunk.start_ts)}
                  className="inline cursor-pointer transition-colors"
                  style={{
                    backgroundColor: isActive
                      ? "rgba(245, 130, 32, 0.2)"
                      : chunk.has_claims
                        ? "rgba(245, 130, 32, 0.07)"
                        : "transparent",
                    color: isActive ? "#f5f5f5" : chunk.has_claims ? "#d4d4d8" : "#71717a",
                    borderRadius: 2,
                    padding: "1px 2px",
                    fontSize: "0.8125rem",
                    lineHeight: 1.6,
                  }}
                  title={
                    chunk.start_ts !== null
                      ? `${formatTimestamp(chunk.start_ts)}`
                      : undefined
                  }
                >
                  {chunk.text}{" "}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
