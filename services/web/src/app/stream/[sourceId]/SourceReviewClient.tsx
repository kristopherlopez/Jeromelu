"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, User, Calendar, Video, PenLine } from "lucide-react";
import type { SourceDetailResponse, SourceListItem } from "@/lib/types";
import YouTubePlayer, { type YouTubePlayerHandle } from "../../components/YouTubePlayer";
import ClaimsList from "../../components/ClaimsList";
import TranscriptPanel from "../../components/TranscriptPanel";

interface Props {
  data: SourceDetailResponse;
  allSources: SourceListItem[];
}

export default function SourceReviewClient({ data, allSources }: Props) {
  const { source, claims, chunks } = data;
  const [currentTime, setCurrentTime] = useState(0);
  const [activeTab, setActiveTab] = useState<"transcript" | "claims">("transcript");
  const playerRef = useRef<YouTubePlayerHandle>(null);

  const handleSeek = useCallback((seconds: number) => {
    playerRef.current?.seekTo(seconds);
    setCurrentTime(seconds);
  }, []);

  // Derive active claim: prefer precise claim-level timestamps, fall back to chunk
  const activeClaimId = useMemo(() => {
    for (const claim of claims) {
      if (
        claim.start_ts !== null &&
        claim.end_ts !== null &&
        currentTime >= claim.start_ts &&
        currentTime < claim.end_ts
      ) {
        return claim.claim_id;
      }
    }
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

  const relatedSources = useMemo(() => {
    const others = allSources.filter((s) => s.source_id !== source.source_id);
    // Prefer same creator, fall back to all other sources
    const sameCreator =
      source.creator_name
        ? others.filter((s) => s.creator_name === source.creator_name)
        : [];
    return (sameCreator.length > 0 ? sameCreator : others).slice(0, 5);
  }, [allSources, source.source_id, source.creator_name]);

  const sourceTypeLabel =
    source.source_type === "youtube" ? "YouTube" : source.source_type;

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
      <div className="flex flex-col lg:flex-row lg:h-[calc(100vh-49px)]">
        {/* Left: Video + Metadata (sticky) */}
        <div className="w-full lg:w-[50%] p-4 lg:p-6 flex flex-col gap-4 lg:sticky lg:top-0 lg:self-start lg:max-h-[calc(100vh-49px)] lg:overflow-y-auto custom-scrollbar">
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

          {/* Source metadata */}
          <div className="flex items-center gap-4 rounded-lg border border-zinc-800 bg-zinc-900/80 px-4 py-3">
            {source.creator_name && (
              <>
                <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                  <User size={14} className="text-zinc-500" />
                  <span className="text-zinc-200">{source.creator_name}</span>
                </div>
                <div className="h-5 w-px bg-zinc-800" />
              </>
            )}
            {source.published_at && (
              <>
                <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                  <Calendar size={14} className="text-zinc-500" />
                  <span className="text-zinc-200">
                    {new Date(source.published_at).toLocaleDateString("en-AU", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </div>
                <div className="h-5 w-px bg-zinc-800" />
              </>
            )}
            <div className="flex items-center gap-1.5 text-xs text-zinc-400">
              <Video size={14} className="text-zinc-500" />
              <span className="text-zinc-200">{sourceTypeLabel}</span>
            </div>
            <div className="h-5 w-px bg-zinc-800" />
            <div className="flex items-center gap-1.5 text-xs text-zinc-400">
              <PenLine size={14} className="text-zinc-500" />
              <span>
                <span className="text-zinc-200">{claims.length}</span> claims
              </span>
            </div>
          </div>

          {/* Related sources */}
          {relatedSources.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                {source.creator_name ? `More from ${source.creator_name}` : "Other sources"}
              </h2>
              {relatedSources.map((s) => (
                <Link
                  key={s.source_id}
                  href={`/stream/${s.source_id}`}
                  className="group flex items-center justify-between rounded-lg border border-zinc-800 px-3 py-2.5 transition-colors hover:border-zinc-600 hover:bg-zinc-900/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-zinc-300 group-hover:text-white truncate">
                      {s.title}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {s.published_at && (
                        <span className="text-[10px] text-zinc-500">
                          {new Date(s.published_at).toLocaleDateString("en-AU", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </span>
                      )}
                      <span
                        className="text-[10px] font-medium"
                        style={{ color: "var(--tigers-orange)" }}
                      >
                        {s.claim_count} claims
                      </span>
                    </div>
                  </div>
                  <ArrowLeft
                    size={12}
                    className="rotate-180 text-zinc-600 group-hover:text-zinc-400 ml-2 flex-shrink-0"
                  />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Right: Tabbed panel (Transcript + Claims) */}
        <div className="w-full lg:w-[50%] p-4 lg:p-6 lg:pl-0 lg:overflow-hidden flex flex-col">
          {/* Tab bar */}
          <div className="flex gap-4 border-b border-zinc-800 mb-0">
            <button
              onClick={() => setActiveTab("transcript")}
              className={`pb-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                activeTab === "transcript"
                  ? "text-[var(--tigers-orange)] border-b-2 border-[var(--tigers-orange)]"
                  : "text-[#71717a] hover:text-zinc-300"
              }`}
            >
              Transcript
            </button>
            <button
              onClick={() => setActiveTab("claims")}
              className={`pb-2 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                activeTab === "claims"
                  ? "text-[var(--tigers-orange)] border-b-2 border-[var(--tigers-orange)]"
                  : "text-[#71717a] hover:text-zinc-300"
              }`}
            >
              Claims ({claims.length})
            </button>
          </div>

          {/* Tab content */}
          <div className="flex-1 min-h-0 overflow-hidden mt-4">
            {activeTab === "transcript" ? (
              <TranscriptPanel
                chunks={chunks}
                claims={claims}
                currentTime={currentTime}
                onSeek={handleSeek}
              />
            ) : (
              <ClaimsList
                claims={claims}
                activeClaimId={activeClaimId}
                onSeek={handleSeek}
              />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
