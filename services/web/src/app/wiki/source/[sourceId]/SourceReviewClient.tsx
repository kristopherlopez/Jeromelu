"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, User, Calendar, Video, PenLine, Hourglass, Smartphone } from "lucide-react";
import type { SourceDetailResponse, Speaker, SourceListItem } from "@/lib/types";
import { apiFetch } from "@/lib/api";
import { useIsYouTubeShort } from "@/lib/useIsYouTubeShort";
import { usePageHeader } from "@/app/components/PageHeaderContext";
import YouTubePlayer, { type YouTubePlayerHandle } from "@/app/components/YouTubePlayer";
import VideoOverlay, { type VideoOverlayHandle } from "@/app/components/VideoOverlay";
import YouTubeFaceOverlay, {
  type YouTubeFaceOverlayHandle,
} from "@/app/components/YouTubeFaceOverlay";
import ClaimsList from "@/app/components/ClaimsList";
import TranscriptPanel from "@/app/components/TranscriptPanel";
import EpisodeTimeline from "@/app/components/EpisodeTimeline";
import FacesPanel from "@/app/components/FacesPanel";

interface Props {
  data: SourceDetailResponse;
  allSources: SourceListItem[];
}

export default function SourceReviewClient({ data, allSources }: Props) {
  const { source, claims, chunks } = data;
  // Speakers is in local state (not a prop reference) because the
  // bulk-assign flow rewrites speaker_person_id on hundreds of rows and
  // the overlay's labels depend on it. Without lifting this, the overlay
  // would refetch the regenerated face-track JSON (via faceTrackVersion)
  // but still resolve every face.person_id against the stale, page-load
  // speaker list — producing the "matched" fallback label instead of
  // the person's name until the user hard-refreshes the page.
  const [speakers, setSpeakers] = useState<Speaker[]>(data.speakers ?? []);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeTab, setActiveTab] = useState<"transcript" | "claims" | "faces">("transcript");
  // Bumped after a successful face cluster assign so the overlay
  // remounts and re-fetches the regenerated face-track JSON. Combined
  // with the API's no-cache header, that's how the per-frame bbox
  // colouring catches up after the operator labels a cluster.
  const [faceTrackVersion, setFaceTrackVersion] = useState(0);

  const refreshSpeakers = useCallback(async () => {
    try {
      const fresh = await apiFetch<SourceDetailResponse>(
        `/api/sources/${source.source_id}`,
      );
      setSpeakers(fresh.speakers ?? []);
    } catch (err) {
      // Non-fatal: the overlay still shows "matched" for un-resolved
      // person_ids, which is a clear "DB has it but UI hasn't caught
      // up yet" signal. A console error is enough — no toast needed.
      console.error("Failed to refresh speakers after cluster assign:", err);
    }
  }, [source.source_id]);
  // Three video surfaces, picked in priority order:
  //   1. YouTubeFaceOverlay — canvas drawn over the YouTube iframe.
  //      Default for any YouTube source with a face-track JSON. The
  //      video file itself is no longer persisted (Chunk 2 of the
  //      ephemeral-video plan).
  //   2. VideoOverlay — legacy path: HTML5 video element + canvas, used
  //      when a stored low-res mp4 still exists in S3 (pre-Chunk-2 row).
  //   3. YouTubePlayer — plain YouTube embed, no overlay (no face-track
  //      yet, or non-YouTube source with no local video).
  const isYouTube = source.source_type === "youtube" && Boolean(source.canonical_url);
  const isShort = useIsYouTubeShort(isYouTube ? source.canonical_url : null);
  const useYouTubeOverlay = isYouTube && Boolean(source.face_track_url);
  const useLegacyOverlay =
    !useYouTubeOverlay && Boolean(source.video_url && source.face_track_url);
  const ytOverlayRef = useRef<YouTubeFaceOverlayHandle>(null);
  const overlayRef = useRef<VideoOverlayHandle>(null);
  const playerRef = useRef<YouTubePlayerHandle>(null);

  const handleSeek = useCallback(
    (seconds: number) => {
      if (useYouTubeOverlay) {
        ytOverlayRef.current?.seekTo(seconds);
      } else if (useLegacyOverlay) {
        overlayRef.current?.seekTo(seconds);
      } else {
        playerRef.current?.seekTo(seconds);
      }
      setCurrentTime(seconds);
    },
    [useYouTubeOverlay, useLegacyOverlay],
  );

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
    source.source_type === "youtube"
      ? isShort
        ? "YouTube · Short"
        : "YouTube"
      : source.source_type;

  const publishedLabel = source.published_at
    ? new Date(source.published_at).toLocaleDateString("en-AU", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : null;

  const { setHeader } = usePageHeader();
  useEffect(() => {
    setHeader({
      backHref: "/wiki?type=sources",
      backLabel: "Back",
      title: source.title,
      meta: (
        <>
          {isShort && (
            <span
              className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
              style={{
                borderColor: "var(--accent)",
                color: "var(--accent)",
                backgroundColor:
                  "color-mix(in srgb, var(--accent) 12%, transparent)",
              }}
              title="This video was uploaded as a YouTube Short (vertical 9:16)"
            >
              <Smartphone size={11} />
              Short
            </span>
          )}
          {publishedLabel && (
            <span
              className="hidden md:inline text-xs"
              style={{ color: "var(--foreground-ghost)" }}
            >
              {publishedLabel}
            </span>
          )}
        </>
      ),
    });
    return () => setHeader(null);
  }, [setHeader, source.title, isShort, publishedLabel]);

  // Sources without chunks haven't been transcribed yet — the video still
  // plays, but transcript and claims tabs need a placeholder so the panel
  // doesn't look broken.
  const isAwaitingTranscript = chunks.length === 0;
  const processingMessage = (() => {
    if (source.transcription_status === "failed") {
      return "Transcription failed for this episode. The video plays but no transcript or claims are available.";
    }
    if (source.ingestion_status !== "completed") {
      return "Scout hasn't finished ingesting this episode yet. Transcript and claims will appear once it's processed.";
    }
    return "This episode is queued for transcription. Transcript and claims will appear once the GPU worker finishes.";
  })();

  return (
    <main>
      {/* Main content */}
      <div className="flex flex-col lg:flex-row lg:h-[calc(100vh-56px)]">
        {/* Left: Video + Metadata (sticky) */}
        <div className="w-full lg:w-[50%] p-4 lg:p-6 flex flex-col gap-4 lg:sticky lg:top-0 lg:self-start lg:max-h-[calc(100vh-56px)] lg:overflow-y-auto custom-scrollbar">
          {useYouTubeOverlay ? (
            <YouTubeFaceOverlay
              key={`yt-${faceTrackVersion}`}
              ref={ytOverlayRef}
              videoUrl={source.canonical_url!}
              faceTrackUrl={source.face_track_url}
              sourceId={source.source_id}
              speakers={speakers ?? []}
              onTimeUpdate={setCurrentTime}
            />
          ) : useLegacyOverlay ? (
            <VideoOverlay
              key={`legacy-${faceTrackVersion}`}
              ref={overlayRef}
              videoUrl={source.video_url!}
              faceTrackUrl={source.face_track_url}
              sourceId={source.source_id}
              speakers={speakers ?? []}
              onTimeUpdate={setCurrentTime}
            />
          ) : source.canonical_url ? (
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

          {/* Episode timeline */}
          <EpisodeTimeline
            claims={claims}
            chunks={chunks}
            currentTime={currentTime}
            onSeek={handleSeek}
          />

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
                  href={`/wiki/source/${s.source_id}`}
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
            {source.face_track_url && (
              <button
                onClick={() => setActiveTab("faces")}
                className="pb-2 text-[11px] font-semibold uppercase tracking-wider transition-colors"
                style={{
                  color: activeTab === "faces" ? "var(--accent)" : "var(--foreground-muted)",
                  borderBottom: activeTab === "faces" ? "2px solid var(--accent)" : "2px solid transparent",
                }}
              >
                Faces
              </button>
            )}
          </div>

          {/* Tab content */}
          <div className="flex-1 min-h-0 overflow-hidden mt-4">
            {isAwaitingTranscript ? (
              <div
                className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border px-6 py-10 text-center"
                style={{
                  borderColor: "var(--border)",
                  backgroundColor: "var(--background-deep)",
                  color: "var(--foreground-secondary)",
                }}
              >
                <Hourglass size={22} style={{ color: "var(--foreground-ghost)" }} />
                <p className="max-w-sm text-sm leading-relaxed">{processingMessage}</p>
              </div>
            ) : activeTab === "transcript" ? (
              <TranscriptPanel
                chunks={chunks}
                claims={claims}
                speakers={speakers ?? []}
                currentTime={currentTime}
                onSeek={handleSeek}
              />
            ) : activeTab === "faces" ? (
              <FacesPanel
                sourceId={source.source_id}
                onSeek={handleSeek}
                onClusterAssigned={() => {
                  // Two refreshes triggered together: the overlay needs
                  // the regenerated face-track JSON (via key remount)
                  // AND the lifted speakers list so the name resolves
                  // against the new speaker_person_id rows. Doing only
                  // one leaves the label stuck on "matched".
                  setFaceTrackVersion((v) => v + 1);
                  void refreshSpeakers();
                }}
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
