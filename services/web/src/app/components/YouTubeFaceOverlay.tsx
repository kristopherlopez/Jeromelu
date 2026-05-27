"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";

import { API_BASE } from "@/lib/api";
import type { FaceTrack, FaceTrackFace, FaceTrackFrame, Speaker } from "@/lib/types";
import { extractVideoId } from "@/lib/youtube";
import ReassignFaceModal from "./ReassignFaceModal";

export interface YouTubeFaceOverlayHandle {
  seekTo: (seconds: number) => void;
}

interface Props {
  videoUrl: string;            // YouTube canonical_url
  faceTrackUrl: string | null;
  sourceId: string;
  speakers: Speaker[];
  onTimeUpdate?: (time: number) => void;
}

interface ClickableFace {
  face: FaceTrackFace;
  rect: { x: number; y: number; width: number; height: number };
  speaker: Speaker | null;
  frameTs: number;
}

declare global {
  interface Window {
    YT: typeof YT;
    onYouTubeIframeAPIReady: () => void;
  }
}

const COLOR_VOICE_FACE = "#22c55e";  // green — pipeline agreed (voice+face)
const COLOR_FACE_ONLY = "#f59e0b";   // amber — face-only attribution
const COLOR_VOICE_ONLY = "#3b82f6";  // blue — voice fired alone, or face ≠ speaker
const COLOR_MANUAL = "#a855f7";      // purple — operator-confirmed via bulk-assign
const COLOR_UNKNOWN = "#737373";     // grey — face has no person_id

function pickColor(
  face: { person_id: string | null },
  activeSpeaker: Speaker | null,
): string {
  if (!face.person_id) return COLOR_UNKNOWN;
  if (!activeSpeaker || !activeSpeaker.speaker_person_id) {
    return COLOR_FACE_ONLY;
  }
  if (face.person_id !== activeSpeaker.speaker_person_id) {
    return COLOR_VOICE_ONLY;
  }
  switch (activeSpeaker.match_method) {
    case "voice+face":
      return COLOR_VOICE_FACE;
    case "face":
      return COLOR_FACE_ONLY;
    case "voice":
      return COLOR_VOICE_ONLY;
    case "manual":
      return COLOR_MANUAL;
    default:
      return COLOR_UNKNOWN;
  }
}

function speakerAt(speakers: Speaker[], ts: number): Speaker | null {
  // Binary search by start_ts. Speakers are expected to be sorted —
  // the caller passes sortedSpeakers. Long sources (3h+) have thousands
  // of turns; the previous linear scan was the hot spot of every rAF
  // tick.
  if (speakers.length === 0) return null;
  let lo = 0;
  let hi = speakers.length - 1;
  let candidate = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    if (speakers[mid].start_ts <= ts) {
      candidate = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (candidate < 0) return null;
  const sp = speakers[candidate];
  return ts <= sp.end_ts ? sp : null;
}

function frameAt(
  frames: FaceTrackFrame[],
  ts: number,
  sampleRate: number,
): FaceTrackFrame | null {
  if (frames.length === 0) return null;
  const tolerance = 1 / sampleRate / 2 + 0.05;
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (frames[mid].ts < ts) lo = mid + 1;
    else hi = mid;
  }
  const candidate = frames[lo];
  const prev = lo > 0 ? frames[lo - 1] : null;
  const best =
    prev && Math.abs(prev.ts - ts) < Math.abs(candidate.ts - ts) ? prev : candidate;
  return Math.abs(best.ts - ts) <= tolerance ? best : null;
}

const YouTubeFaceOverlay = forwardRef<YouTubeFaceOverlayHandle, Props>(
  ({ videoUrl, faceTrackUrl, sourceId, speakers, onTimeUpdate }, ref) => {
    const wrapRef = useRef<HTMLDivElement>(null);
    const playerHostRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const playerRef = useRef<YT.Player | null>(null);
    const animationRef = useRef<number | null>(null);
    // Throttle the per-frame currentTime emit to ~10 Hz. Without this,
    // every rAF tick (~60 Hz) re-renders the entire review page (transcript,
    // claims list, episode timeline) — sub-100ms granularity is wasted on
    // those consumers.
    const lastEmittedTsRef = useRef<number>(-Infinity);
    // The draw callback recreates on dep changes, but the rAF loop must
    // not — restarting it every state change leaks animation handles. The
    // loop reads from this ref so it picks up the latest draw without
    // re-scheduling.
    const drawRef = useRef<() => void>(() => {});
    const [playerReady, setPlayerReady] = useState(false);
    const [faceTrack, setFaceTrack] = useState<FaceTrack | null>(null);
    const [trackError, setTrackError] = useState<string | null>(null);
    const [clickableFaces, setClickableFaces] = useState<ClickableFace[]>([]);
    const [reassignTarget, setReassignTarget] = useState<ClickableFace | null>(null);

    const videoId = extractVideoId(videoUrl);

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        playerRef.current?.seekTo(seconds, true);
      },
    }));

    useEffect(() => {
      if (!faceTrackUrl) {
        setFaceTrack(null);
        return;
      }
      const url = faceTrackUrl.startsWith("/")
        ? `${API_BASE}${faceTrackUrl}`
        : faceTrackUrl;
      let cancelled = false;
      fetch(url)
        .then((r) => {
          if (!r.ok) throw new Error(`face-track fetch failed: ${r.status}`);
          return r.json();
        })
        .then((j: FaceTrack) => {
          if (!cancelled) setFaceTrack(j);
        })
        .catch((e: unknown) => {
          if (!cancelled) setTrackError(String(e));
        });
      return () => {
        cancelled = true;
      };
    }, [faceTrackUrl]);

    const sampleRate = faceTrack?.sample_rate ?? 1.0;
    const frames = useMemo(() => faceTrack?.frames ?? [], [faceTrack]);
    // Source pixel space the bboxes were extracted in. v4 JSONs carry
    // these directly; v3 falls back to a 360p 16:9 default that matches
    // the historical Scout download quality (DEFAULT_QUALITY="360" in
    // services/api/app/scout/media/video.py). Wrong only if a 240p/480p
    // source slipped through — would skew bbox positions but not break.
    const sourceW = faceTrack?.frame_width ?? 640;
    const sourceH = faceTrack?.frame_height ?? 360;
    const sourceDuration = faceTrack?.duration_seconds ?? 0;

    const sortedSpeakers = useMemo(
      () => [...speakers].sort((a, b) => a.start_ts - b.start_ts),
      [speakers],
    );

    // O(1) person_id → name lookup. Replaces the per-face Array.find()
    // that ran on every draw tick — for long sources (2k+ speakers,
    // 3-4 faces/frame, 60 fps), the find() was hundreds of thousands of
    // iterations per second of nothing but property reads.
    const personNameById = useMemo(() => {
      const m = new Map<string, string>();
      for (const sp of speakers) {
        if (sp.speaker_person_id && sp.speaker_person_name) {
          m.set(sp.speaker_person_id, sp.speaker_person_name);
        }
      }
      return m;
    }, [speakers]);

    // Cache the last-drawn state so the rAF loop can early-return when
    // neither the matched frame nor the active speaker has changed.
    // YouTube emits time updates at video-frame rate (60Hz) but the
    // face-track is sampled at 1Hz — without this guard, 59 out of every
    // 60 ticks redrew the exact same bboxes.
    const lastDrawKeyRef = useRef<string>("");

    const draw = useCallback(() => {
      const canvas = canvasRef.current;
      const player = playerRef.current;
      const wrap = wrapRef.current;
      if (!canvas || !player || !wrap || !playerReady) return;
      if (typeof player.getCurrentTime !== "function") return;

      // YT.Player replaces playerHostRef's div with an iframe at init,
      // leaving the ref pointing at a detached node — its bounding rect
      // is 0×0. The wrapper div is the stable parent; both the iframe
      // and the canvas fill it via `inset-0 absolute`, so its rect is
      // also the canvas's render size.
      const rect = wrap.getBoundingClientRect();
      const resized =
        canvas.width !== rect.width || canvas.height !== rect.height;
      if (resized) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }

      // Ad detection: the IFrame API has no public ad event, but
      // getCurrentTime() reports the *currently playing media*'s clock
      // — during an ad, that's the ad's elapsed time, not the source's.
      // The cheapest signal we have is duration drift: when an ad is
      // loaded, getDuration() differs from the source by minutes. Skip
      // drawing entirely so non-Premium reviewers don't see boxes
      // smeared over ad pixels at the wrong timestamps.
      const playerDur = player.getDuration?.() ?? 0;
      const inAd =
        sourceDuration > 0 &&
        playerDur > 0 &&
        Math.abs(playerDur - sourceDuration) > 5;
      if (inAd) {
        const ctxAd = canvas.getContext("2d");
        if (ctxAd) ctxAd.clearRect(0, 0, canvas.width, canvas.height);
        lastDrawKeyRef.current = "ad";
        setClickableFaces((prev) => (prev.length === 0 ? prev : []));
        return;
      }

      const ts = player.getCurrentTime();
      if (Math.abs(ts - lastEmittedTsRef.current) >= 0.1) {
        lastEmittedTsRef.current = ts;
        onTimeUpdate?.(ts);
      }

      const frame = frameAt(frames, ts, sampleRate);
      const active = speakerAt(sortedSpeakers, ts);

      // Early-return when nothing visible has changed. Bboxes and labels
      // only depend on (frame, active speaker, canvas size) — if all
      // three are the same as the last draw, the existing canvas is
      // still correct and we'd just be redrawing identical pixels.
      const drawKey = frame
        ? `${frame.ts}|${active?.segment_id ?? ""}|${canvas.width}x${canvas.height}`
        : `none|${active?.segment_id ?? ""}|${canvas.width}x${canvas.height}`;
      if (!resized && drawKey === lastDrawKeyRef.current) return;
      lastDrawKeyRef.current = drawKey;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (!frame) {
        setClickableFaces((prev) => (prev.length === 0 ? prev : []));
        return;
      }

      // Source video and iframe are both expected 16:9 — direct scale.
      // (If we ever overlay vertical/Short content, letterbox math goes
      // here.)
      const sx = canvas.width / sourceW;
      const sy = canvas.height / sourceH;

      ctx.lineWidth = 2;
      ctx.font = "12px system-ui, sans-serif";

      const nextClickable: ClickableFace[] = [];

      for (const face of frame.faces) {
        const [x1, y1, x2, y2] = face.bbox;
        const x = x1 * sx;
        const y = y1 * sy;
        const w = (x2 - x1) * sx;
        const h = (y2 - y1) * sy;

        const color = pickColor(face, active);
        ctx.strokeStyle = color;
        ctx.strokeRect(x, y, w, h);

        const personName = face.person_id
          ? personNameById.get(face.person_id)
          : undefined;
        const label = personName ?? (face.person_id ? "matched" : "?");
        const conf =
          face.similarity != null ? ` ${(face.similarity * 100).toFixed(0)}%` : "";
        const text = `${label}${conf}`;
        const metrics = ctx.measureText(text);
        const padX = 4;
        const padY = 2;
        const labelW = metrics.width + padX * 2;
        const labelH = 16;
        const labelY = y - labelH - 2 >= 0 ? y - labelH - 2 : y + h + 2;

        ctx.fillStyle = color;
        ctx.fillRect(x, labelY, labelW, labelH);
        ctx.fillStyle = "#000";
        ctx.fillText(text, x + padX, labelY + labelH - padY - 3);

        nextClickable.push({
          face,
          rect: { x, y, width: w, height: h },
          speaker: active,
          frameTs: frame.ts,
        });
      }

      setClickableFaces((prev) => {
        if (prev.length !== nextClickable.length) return nextClickable;
        for (let i = 0; i < prev.length; i++) {
          const a = prev[i];
          const b = nextClickable[i];
          if (
            a.rect.x !== b.rect.x ||
            a.rect.y !== b.rect.y ||
            a.rect.width !== b.rect.width ||
            a.rect.height !== b.rect.height ||
            a.face.person_id !== b.face.person_id ||
            a.speaker?.segment_id !== b.speaker?.segment_id
          ) {
            return nextClickable;
          }
        }
        return prev;
      });
    }, [
      frames,
      sampleRate,
      sortedSpeakers,
      personNameById,
      playerReady,
      sourceW,
      sourceH,
      sourceDuration,
      onTimeUpdate,
    ]);

    // Keep the ref pointed at the latest draw closure. The rAF loop
    // dereferences this on every tick, so changing `draw` doesn't require
    // restarting the loop or risking a stale closure.
    useEffect(() => {
      drawRef.current = draw;
    }, [draw]);

    const startLoop = useCallback(() => {
      if (animationRef.current != null) return;
      const tick = () => {
        drawRef.current();
        animationRef.current = requestAnimationFrame(tick);
      };
      animationRef.current = requestAnimationFrame(tick);
    }, []);

    const stopLoop = useCallback(() => {
      if (animationRef.current != null) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    }, []);

    // Boot the YouTube iframe API and instantiate the player.
    useEffect(() => {
      if (!videoId) return;

      const initPlayer = () => {
        if (!playerHostRef.current) return;
        playerRef.current = new window.YT.Player(playerHostRef.current, {
          videoId,
          playerVars: {
            enablejsapi: 1,
            rel: 0,
            modestbranding: 1,
          },
          events: {
            onReady: () => {
              setPlayerReady(true);
              drawRef.current();
            },
            onStateChange: (e: YT.OnStateChangeEvent) => {
              if (e.data === window.YT.PlayerState.PLAYING) {
                startLoop();
              } else {
                stopLoop();
                drawRef.current();
              }
            },
          },
        });
      };

      if (window.YT?.Player) {
        initPlayer();
      } else {
        const existing = document.getElementById("yt-iframe-api");
        if (!existing) {
          const tag = document.createElement("script");
          tag.id = "yt-iframe-api";
          tag.src = "https://www.youtube.com/iframe_api";
          document.head.appendChild(tag);
        }
        window.onYouTubeIframeAPIReady = initPlayer;
      }

      return () => {
        stopLoop();
        playerRef.current?.destroy();
        playerRef.current = null;
        setPlayerReady(false);
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [videoId]);

    if (!videoId) {
      return (
        <div
          className="flex aspect-video items-center justify-center rounded-lg border"
          style={{
            borderColor: "var(--border)",
            backgroundColor: "var(--background-deep)",
            color: "var(--foreground-ghost)",
          }}
        >
          Could not parse YouTube video id from URL
        </div>
      );
    }

    return (
      <div
        ref={wrapRef}
        className="ytfo-wrap relative aspect-video w-full shrink-0 overflow-hidden rounded-lg border"
        style={{ borderColor: "var(--border)" }}
      >
        <style>{`.ytfo-wrap iframe { position: absolute; inset: 0; width: 100%; height: 100%; }`}</style>
        <div ref={playerHostRef} className="absolute inset-0" />
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full"
        />
        {/* Clickable face buttons. Wrapper has pointer-events: none so
            clicks outside boxes fall through to the YouTube iframe (so
            its native play/pause/controls still respond). Each button
            re-enables pointer-events for its own bbox. */}
        <div className="pointer-events-none absolute inset-0">
          {clickableFaces.map((cf, idx) => (
            <button
              key={`${cf.frameTs}-${idx}`}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (!cf.speaker) return;
                playerRef.current?.pauseVideo();
                setReassignTarget(cf);
              }}
              title={
                cf.speaker
                  ? "Click to reassign this turn"
                  : "No speaker turn at this frame"
              }
              className="pointer-events-auto absolute cursor-pointer"
              style={{
                left: cf.rect.x,
                top: cf.rect.y,
                width: cf.rect.width,
                height: cf.rect.height,
                background: "transparent",
                border: "none",
                padding: 0,
              }}
              aria-label="Reassign face"
            />
          ))}
        </div>
        {!playerReady && (
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{
              backgroundColor: "var(--background-deep)",
              color: "var(--foreground-ghost)",
            }}
          >
            Loading player...
          </div>
        )}
        {trackError && (
          <div className="absolute right-2 top-2 rounded bg-red-900/70 px-2 py-1 text-xs text-red-100">
            face-track error: {trackError}
          </div>
        )}
        {reassignTarget && reassignTarget.speaker && (
          <ReassignFaceModal
            sourceId={sourceId}
            speaker={reassignTarget.speaker}
            frameTs={reassignTarget.frameTs}
            bbox={reassignTarget.face.bbox}
            onClose={() => setReassignTarget(null)}
            onSaved={() => {
              setReassignTarget(null);
              window.location.reload();
            }}
          />
        )}
      </div>
    );
  },
);

YouTubeFaceOverlay.displayName = "YouTubeFaceOverlay";
export default YouTubeFaceOverlay;
