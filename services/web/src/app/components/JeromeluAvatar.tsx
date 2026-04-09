"use client";

import { useRef, useEffect, useState } from "react";

interface JeromeluAvatarProps {
  size?: number;
  clipSrc?: string;
  light?: boolean;
}

const RING_DARK = {
  glow: "0 0 20px rgba(212,135,74,0.20), 0 0 40px rgba(212,135,74,0.10)",
  border: "2px solid rgba(212,135,74,0.35)",
  fallbackBg: "rgba(212,135,74,0.15)",
  fallbackBorder: "2px solid rgba(212,135,74,0.35)",
};

const RING_LIGHT = {
  glow: "0 2px 12px rgba(120,60,30,0.15), 0 0 24px rgba(120,60,30,0.08)",
  border: "2px solid rgba(120,60,30,0.30)",
  fallbackBg: "rgba(120,60,30,0.10)",
  fallbackBorder: "2px solid rgba(120,60,30,0.30)",
};

const AVATAR_CDN_BASE = process.env.NEXT_PUBLIC_AVATAR_CDN_BASE || "";
const DEFAULT_CLIP = AVATAR_CDN_BASE
  ? `${AVATAR_CDN_BASE}/avatar/clips/idle-1-1.mp4`
  : "/avatar/clips/idle-1-1.mp4";

export function JeromeluAvatar({ size = 140, clipSrc, light }: JeromeluAvatarProps) {
  const ring = light ? RING_LIGHT : RING_DARK;
  const [videoFailed, setVideoFailed] = useState(false);
  const videoARef = useRef<HTMLVideoElement>(null);
  const videoBRef = useRef<HTMLVideoElement>(null);
  const [activeVideo, setActiveVideo] = useState<"a" | "b">("a");
  const currentSrcRef = useRef<string>(clipSrc || DEFAULT_CLIP);

  const src = clipSrc || DEFAULT_CLIP;

  // Crossfade when clipSrc changes
  useEffect(() => {
    if (src === currentSrcRef.current) return;
    currentSrcRef.current = src;

    const incoming = activeVideo === "a" ? videoBRef.current : videoARef.current;
    if (incoming) {
      incoming.src = src;
      incoming.load();
      incoming.play().catch(() => {});
    }

    setActiveVideo((prev) => (prev === "a" ? "b" : "a"));
  }, [src, activeVideo]);

  if (videoFailed) {
    return (
      <div
        className="flex items-center justify-center rounded-full font-bold"
        style={{
          width: size,
          height: size,
          backgroundColor: ring.fallbackBg,
          color: light ? "#5c4030" : "var(--accent)",
          fontSize: size * 0.4,
          boxShadow: ring.glow,
          border: ring.fallbackBorder,
        }}
      >
        J
      </div>
    );
  }

  return (
    <div
      className="relative shrink-0"
      style={{
        width: size,
        height: size,
        transition: "width 900ms cubic-bezier(0.4, 0, 0.2, 1), height 900ms cubic-bezier(0.4, 0, 0.2, 1)",
      }}
    >
      {/* Outer glow ring */}
      <div
        className="absolute inset-0 rounded-full"
        style={{ boxShadow: ring.glow }}
      />

      {/* Border ring */}
      <div
        className="absolute inset-0 rounded-full"
        style={{ border: ring.border }}
      />

      {/* Dual video elements for crossfade */}
      <div
        className="relative overflow-hidden rounded-full"
        style={{
          width: size,
          height: size,
          transition: "width 900ms cubic-bezier(0.4, 0, 0.2, 1), height 900ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        <video
          ref={videoARef}
          autoPlay
          loop
          muted
          playsInline
          onError={() => setVideoFailed(true)}
          className="absolute inset-0 h-full w-full object-cover transition-opacity duration-300"
          style={{ opacity: activeVideo === "a" ? 1 : 0 }}
          src={src}
        />
        <video
          ref={videoBRef}
          loop
          muted
          playsInline
          className="absolute inset-0 h-full w-full object-cover transition-opacity duration-300"
          style={{ opacity: activeVideo === "b" ? 1 : 0 }}
        />
      </div>
    </div>
  );
}
