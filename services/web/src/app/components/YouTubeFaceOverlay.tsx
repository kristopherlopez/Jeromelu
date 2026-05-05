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

const COLOR_VOICE_FACE = "#22c55e";
const COLOR_FACE_ONLY = "#f59e0b";
const COLOR_VOICE_ONLY = "#3b82f6";
const COLOR_UNKNOWN = "#737373";

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
    default:
      return COLOR_UNKNOWN;
  }
}

function speakerAt(speakers: Speaker[], ts: number): Speaker | null {
  for (const sp of speakers) {
    if (ts >= sp.start_ts && ts <= sp.end_ts) return sp;
  }
  return null;
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

function extractVideoId(url: string): string | null {
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtu.be")) return u.pathname.slice(1);
    return u.searchParams.get("v");
  } catch {
    return null;
  }
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
    // services/api/app/scout/video.py). Wrong only if a 240p/480p
    // source slipped through — would skew bbox positions but not break.
    const sourceW = faceTrack?.frame_width ?? 640;
    const sourceH = faceTrack?.frame_height ?? 360;

    const sortedSpeakers = useMemo(
      () => [...speakers].sort((a, b) => a.start_ts - b.start_ts),
      [speakers],
    );

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
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const ts = player.getCurrentTime();
      if (Math.abs(ts - lastEmittedTsRef.current) >= 0.1) {
        lastEmittedTsRef.current = ts;
        onTimeUpdate?.(ts);
      }

      const frame = frameAt(frames, ts, sampleRate);
      if (!frame) {
        setClickableFaces((prev) => (prev.length === 0 ? prev : []));
        return;
      }

      // Source video and iframe are both expected 16:9 — direct scale.
      // (If we ever overlay vertical/Short content, letterbox math goes
      // here.)
      const sx = canvas.width / sourceW;
      const sy = canvas.height / sourceH;

      const active = speakerAt(sortedSpeakers, ts);

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

        const lookup = sortedSpeakers.find(
          (sp) => sp.speaker_person_id && sp.speaker_person_id === face.person_id,
        );
        const label = lookup?.speaker_person_name ?? (face.person_id ? "matched" : "?");
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
      playerReady,
      sourceW,
      sourceH,
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
