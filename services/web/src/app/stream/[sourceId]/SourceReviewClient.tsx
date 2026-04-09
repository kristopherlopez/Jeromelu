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
      <div className="flex items-center gap-3 border-b px-4 py-3 lg:px-6" style={{ borderColor: "var(--border)" }}>
        <Link
          href="/stream"
          className="flex items-center gap-1 text-sm transition-colors" style={{ color: "var(--foreground-secondary)" }}
        >
          <ArrowLeft size={16} />
          Back
        </Link>
        <h1 className="flex-1 truncate text-sm font-semibold" style={{ color: "var(--foreground)" }}>
          {source.title}
        </h1>
        {source.published_at && (
          <span className="hidden text-xs sm:block" style={{ color: "var(--foreground-ghost)" }}>
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
            <div className="flex aspect-video items-center justify-center rounded-lg border" style={{ borderColor: "var(--border)", backgroundColor: "var(--background-deep)", color: "var(--foreground-ghost)" }}>
              No video URL available
            </div>
          )}

          {/* Source metadata */}
          <div className="flex items-center gap-4 rounded-lg border px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--background-deep)" }}>
            {source.creator_name && (
              <>
                <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--foreground-secondary)" }}>
                  <User size={14} style={{ color: "var(--foreground-ghost)" }} />
                  <span style={{ color: "var(--foreground)" }}>{source.creator_name}</span>
                </div>
                <div className="h-5 w-px" style={{ backgroundColor: "var(--border)" }} />
              </>
            )}
            {source.published_at && (
              <>
                <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--foreground-secondary)" }}>
                  <Calendar size={14} style={{ color: "var(--foreground-ghost)" }} />
                  <span style={{ color: "var(--foreground)" }}>
                    {new Date(source.published_at).toLocaleDateString("en-AU", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </div>
                <div className="h-5 w-px" style={{ backgroundColor: "var(--border)" }} />
              </>
            )}
            <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--foreground-secondary)" }}>
              <Video size={14} style={{ color: "var(--foreground-ghost)" }} />
              <span style={{ color: "var(--foreground)" }}>{sourceTypeLabel}</span>
            </div>
            <div className="h-5 w-px" style={{ backgroundColor: "var(--border)" }} />
            <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--foreground-secondary)" }}>
              <PenLine size={14} style={{ color: "var(--foreground-ghost)" }} />
              <span>
                <span style={{ color: "var(--foreground)" }}>{claims.length}</span> claims
              </span>
            </div>
          </div>

          {/* Related sources */}
          {relatedSources.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--foreground-ghost)" }}>
                {source.creator_name ? `More from ${source.creator_name}` : "Other sources"}
              </h2>
              {relatedSources.map((s) => (
                <Link
                  key={s.source_id}
                  href={`/stream/${s.source_id}`}
                  className="group flex items-center justify-between rounded-lg border px-3 py-2.5 transition-colors" style={{ borderColor: "var(--border)" }}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium group-hover:text-white truncate" style={{ color: "var(--foreground)" }}>
                      {s.title}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {s.published_at && (
                        <span className="text-[10px]" style={{ color: "var(--foreground-ghost)" }}>
                          {new Date(s.published_at).toLocaleDateString("en-AU", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </span>
                      )}
                      <span
                        className="text-[10px] font-medium"
                        style={{ color: "var(--accent)" }}
                      >
                        {s.claim_count} claims
                      </span>
                    </div>
                  </div>
                  <ArrowLeft
                    size={12}
                    className="rotate-180 ml-2 flex-shrink-0" style={{ color: "var(--foreground-ghost)" }}
                  />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Right: Tabbed panel (Transcript + Claims) */}
        <div className="w-full lg:w-[50%] p-4 lg:p-6 lg:pl-0 lg:overflow-hidden flex flex-col">
          {/* Tab bar */}
          <div className="flex gap-4 border-b mb-0" style={{ borderColor: "var(--border)" }}>
            <button
              onClick={() => setActiveTab("transcript")}
              className="pb-2 text-[11px] font-semibold uppercase tracking-wider transition-colors"
              style={{
                color: activeTab === "transcript" ? "var(--accent)" : "var(--foreground-muted)",
                borderBottom: activeTab === "transcript" ? "2px solid var(--accent)" : "2px solid transparent",
              }}
            >
              Transcript
            </button>
            <button
              onClick={() => setActiveTab("claims")}
              className="pb-2 text-[11px] font-semibold uppercase tracking-wider transition-colors"
              style={{
                color: activeTab === "claims" ? "var(--accent)" : "var(--foreground-muted)",
                borderBottom: activeTab === "claims" ? "2px solid var(--accent)" : "2px solid transparent",
              }}
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
