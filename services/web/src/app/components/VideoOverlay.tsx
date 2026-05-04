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
import type { FaceTrack, FaceTrackFrame, Speaker } from "@/lib/types";

export interface VideoOverlayHandle {
  seekTo: (seconds: number) => void;
}

interface Props {
  videoUrl: string;
  faceTrackUrl: string | null;
  speakers: Speaker[];
  onTimeUpdate?: (time: number) => void;
}

// Match-method colors.
// - voice+face: agreement across both modalities → highest trust.
// - face: face fired alone for this turn → medium trust.
// - voice: voice fired alone — face is on screen but not the speaker →
//          paint light-blue to flag "known person, not currently speaking".
// - none/manual: grey.
const COLOR_VOICE_FACE = "#22c55e";  // green
const COLOR_FACE_ONLY = "#f59e0b";   // amber
const COLOR_VOICE_ONLY = "#3b82f6";  // blue (face on screen but voice attributes elsewhere)
const COLOR_UNKNOWN = "#737373";     // grey

function pickColor(
  face: { person_id: string | null },
  activeSpeaker: Speaker | null,
): string {
  if (!face.person_id) return COLOR_UNKNOWN;
  if (!activeSpeaker || !activeSpeaker.speaker_person_id) {
    // Face matched but the active speaker turn has no resolved person —
    // we drew the face but don't know its relation to the speaker.
    return COLOR_FACE_ONLY;
  }
  if (face.person_id !== activeSpeaker.speaker_person_id) {
    // Face matches a known person, but they aren't the current speaker.
    return COLOR_VOICE_ONLY;
  }
  // Face is the current speaker — colour by how the speaker was identified.
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
  // Linear scan; sample sizes here are well under 1k turns.
  for (const sp of speakers) {
    if (ts >= sp.start_ts && ts <= sp.end_ts) return sp;
  }
  return null;
}

function frameAt(frames: FaceTrackFrame[], ts: number, sampleRate: number): FaceTrackFrame | null {
  if (frames.length === 0) return null;
  // Frames are sorted by ts; binary-search the closest entry within
  // half a sample interval. Outside that window, we return null so the
  // overlay clears (rather than persisting a stale box).
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

const VideoOverlay = forwardRef<VideoOverlayHandle, Props>(
  ({ videoUrl, faceTrackUrl, speakers, onTimeUpdate }, ref) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationRef = useRef<number | null>(null);
    const [faceTrack, setFaceTrack] = useState<FaceTrack | null>(null);
    const [trackError, setTrackError] = useState<string | null>(null);
    const [videoSize, setVideoSize] = useState<{ w: number; h: number } | null>(null);

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        const v = videoRef.current;
        if (!v) return;
        v.currentTime = seconds;
      },
    }));

    // Fetch the face-track JSON once. The API returns a relative path
    // (`/api/sources/.../face-track`) for the proxied artefact; absolute
    // URLs are used as-is (e.g. if we ever switch to direct S3 with a
    // CORS policy).
    useEffect(() => {
      if (!faceTrackUrl) {
        setFaceTrack(null);
        return;
      }
      const url = faceTrackUrl.startsWith("/") ? `${API_BASE}${faceTrackUrl}` : faceTrackUrl;
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
    const frames = faceTrack?.frames ?? [];

    // Sort speakers once for reuse in the inner loop.
    const sortedSpeakers = useMemo(
      () => [...speakers].sort((a, b) => a.start_ts - b.start_ts),
      [speakers],
    );

    const draw = useCallback(() => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) return;

      // Match canvas pixel size to the rendered display size.
      // (Avoids the 300x150 default ignoring the wrapper's aspect-ratio.)
      const rect = video.getBoundingClientRect();
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const ts = video.currentTime;
      const frame = frameAt(frames, ts, sampleRate);
      if (!frame) return;

      const sourceW = video.videoWidth || (videoSize?.w ?? rect.width);
      const sourceH = video.videoHeight || (videoSize?.h ?? rect.height);
      if (!sourceW || !sourceH) return;

      const sx = canvas.width / sourceW;
      const sy = canvas.height / sourceH;

      const active = speakerAt(sortedSpeakers, ts);

      ctx.lineWidth = 2;
      ctx.font = "12px system-ui, sans-serif";

      for (const face of frame.faces) {
        const [x1, y1, x2, y2] = face.bbox;
        const x = x1 * sx;
        const y = y1 * sy;
        const w = (x2 - x1) * sx;
        const h = (y2 - y1) * sy;

        const color = pickColor(face, active);
        ctx.strokeStyle = color;
        ctx.strokeRect(x, y, w, h);

        // Label badge above the box, or below if the box is at the top.
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
      }
    }, [frames, sampleRate, sortedSpeakers, videoSize]);

    // Animation loop — runs whenever the video is playing.
    const tick = useCallback(() => {
      draw();
      const v = videoRef.current;
      if (v) onTimeUpdate?.(v.currentTime);
      animationRef.current = requestAnimationFrame(tick);
    }, [draw, onTimeUpdate]);

    const startLoop = useCallback(() => {
      if (animationRef.current != null) return;
      animationRef.current = requestAnimationFrame(tick);
    }, [tick]);

    const stopLoop = useCallback(() => {
      if (animationRef.current != null) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    }, []);

    useEffect(() => {
      const v = videoRef.current;
      if (!v) return;
      const onPlay = () => startLoop();
      const onPause = () => {
        stopLoop();
        // Final draw + emit so the transcript stays in sync after a seek.
        draw();
        onTimeUpdate?.(v.currentTime);
      };
      const onSeeked = () => {
        draw();
        onTimeUpdate?.(v.currentTime);
      };
      const onMeta = () => setVideoSize({ w: v.videoWidth, h: v.videoHeight });
      v.addEventListener("play", onPlay);
      v.addEventListener("pause", onPause);
      v.addEventListener("ended", onPause);
      v.addEventListener("seeked", onSeeked);
      v.addEventListener("loadedmetadata", onMeta);
      return () => {
        stopLoop();
        v.removeEventListener("play", onPlay);
        v.removeEventListener("pause", onPause);
        v.removeEventListener("ended", onPause);
        v.removeEventListener("seeked", onSeeked);
        v.removeEventListener("loadedmetadata", onMeta);
      };
    }, [startLoop, stopLoop, draw, onTimeUpdate]);

    return (
      <div
        className="vo-wrap relative aspect-video w-full shrink-0 overflow-hidden rounded-lg border"
        style={{ borderColor: "var(--border)" }}
      >
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          preload="metadata"
          className="absolute inset-0 h-full w-full bg-black"
        />
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full"
        />
        {trackError && (
          <div className="absolute right-2 top-2 rounded bg-red-900/70 px-2 py-1 text-xs text-red-100">
            face-track error: {trackError}
          </div>
        )}
      </div>
    );
  },
);

VideoOverlay.displayName = "VideoOverlay";
export default VideoOverlay;
