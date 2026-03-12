"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import type { SourceDetailResponse } from "@/lib/types";
import YouTubePlayer, { type YouTubePlayerHandle } from "../../components/YouTubePlayer";
import ClaimsList from "../../components/ClaimsList";
import TranscriptPanel from "../../components/TranscriptPanel";

interface Props {
  data: SourceDetailResponse;
}

export default function SourceReviewClient({ data }: Props) {
  const { source, claims, chunks } = data;
  const [currentTime, setCurrentTime] = useState(0);
  const playerRef = useRef<YouTubePlayerHandle>(null);

  const handleSeek = useCallback((seconds: number) => {
    playerRef.current?.seekTo(seconds);
    setCurrentTime(seconds);
  }, []);

  // Derive active claim: find claim whose earliest chunk contains currentTime
  const activeClaimId = useMemo(() => {
    for (const claim of claims) {
      for (const chunk of claim.chunks) {
        if (
          chunk.start_ts !== null &&
          chunk.end_ts !== null &&
          currentTime >= chunk.start_ts &&
          currentTime < chunk.end_ts
        ) {
          return claim.claim_id;
        }
      }
    }
    return null;
  }, [claims, currentTime]);

  return (
    <main className="min-h-screen">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-zinc-800 px-4 py-3 lg:px-6">
        <Link
          href="/stream"
          className="flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </Link>
        <h1 className="flex-1 truncate text-sm font-semibold text-zinc-200">
          {source.title}
        </h1>
        {source.published_at && (
          <span className="hidden text-xs text-zinc-500 sm:block">
            {new Date(source.published_at).toLocaleDateString("en-AU", {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </span>
        )}
      </div>

      {/* Main content */}
      <div className="flex flex-col lg:flex-row">
        {/* Left: Video */}
        <div className="w-full lg:w-[55%] lg:sticky lg:top-0 lg:self-start p-4 lg:p-6">
          {source.canonical_url ? (
            <YouTubePlayer
              ref={playerRef}
              videoUrl={source.canonical_url}
              onTimeUpdate={setCurrentTime}
            />
          ) : (
            <div className="flex aspect-video items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-500">
              No video URL available
            </div>
          )}
        </div>

        {/* Right: Claims */}
        <div className="w-full lg:w-[45%] p-4 lg:p-6 lg:pl-0 lg:max-h-screen lg:overflow-hidden flex flex-col">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Claims ({claims.length})
          </h2>
          <div className="flex-1 min-h-0">
            <ClaimsList
              claims={claims}
              activeClaimId={activeClaimId}
              onSeek={handleSeek}
            />
          </div>
        </div>
      </div>

      {/* Transcript */}
      <div className="px-4 pb-6 lg:px-6">
        <TranscriptPanel
          chunks={chunks}
          currentTime={currentTime}
          onSeek={handleSeek}
        />
      </div>
    </main>
  );
}
