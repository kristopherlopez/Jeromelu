"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

export interface YouTubePlayerHandle {
  seekTo: (seconds: number) => void;
}

interface Props {
  videoUrl: string;
  onTimeUpdate?: (time: number) => void;
}

declare global {
  interface Window {
    YT: typeof YT;
    onYouTubeIframeAPIReady: () => void;
  }
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

const YouTubePlayer = forwardRef<YouTubePlayerHandle, Props>(
  ({ videoUrl, onTimeUpdate }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const playerRef = useRef<YT.Player | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [ready, setReady] = useState(false);

    const videoId = extractVideoId(videoUrl);

    const startPolling = useCallback(() => {
      if (intervalRef.current) return;
      intervalRef.current = setInterval(() => {
        if (playerRef.current?.getCurrentTime) {
          onTimeUpdate?.(playerRef.current.getCurrentTime());
        }
      }, 500);
    }, [onTimeUpdate]);

    const stopPolling = useCallback(() => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }, []);

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        playerRef.current?.seekTo(seconds, true);
      },
    }));

    useEffect(() => {
      if (!videoId) return;

      const initPlayer = () => {
        if (!containerRef.current) return;
        playerRef.current = new window.YT.Player(containerRef.current, {
          videoId,
          playerVars: {
            enablejsapi: 1,
            rel: 0,
            modestbranding: 1,
          },
          events: {
            onReady: () => setReady(true),
            onStateChange: (e: YT.OnStateChangeEvent) => {
              if (e.data === window.YT.PlayerState.PLAYING) {
                startPolling();
              } else {
                stopPolling();
                // Report final time on pause/end
                if (playerRef.current?.getCurrentTime) {
                  onTimeUpdate?.(playerRef.current.getCurrentTime());
                }
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
        stopPolling();
        playerRef.current?.destroy();
        playerRef.current = null;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [videoId]);

    if (!videoId) {
      return (
        <div className="flex aspect-video items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-500">
          No video URL
        </div>
      );
    }

    return (
      <div className="yt-player-wrap relative aspect-video w-full shrink-0 overflow-hidden rounded-lg border border-zinc-800">
        <style>{`.yt-player-wrap iframe { position: absolute; inset: 0; width: 100%; height: 100%; }`}</style>
        <div ref={containerRef} className="absolute inset-0" />
        {!ready && (
          <div className="absolute inset-0 flex items-center justify-center bg-zinc-900 text-zinc-500">
            Loading player...
          </div>
        )}
      </div>
    );
  }
);

YouTubePlayer.displayName = "YouTubePlayer";
export default YouTubePlayer;
