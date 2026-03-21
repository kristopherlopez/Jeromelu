"use client";

import { useRef, useEffect, useState } from "react";

interface JeromeluAvatarProps {
  size?: number;
  clipSrc?: string;
}

export function JeromeluAvatar({ size = 140, clipSrc }: JeromeluAvatarProps) {
  const [videoFailed, setVideoFailed] = useState(false);
  const videoARef = useRef<HTMLVideoElement>(null);
  const videoBRef = useRef<HTMLVideoElement>(null);
  const [activeVideo, setActiveVideo] = useState<"a" | "b">("a");
  const currentSrcRef = useRef<string>(clipSrc || "/avatar/breathing1.mp4");

  const src = clipSrc || "/avatar/breathing1.mp4";

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
          backgroundColor: "rgba(245, 130, 32, 0.15)",
          color: "var(--tigers-orange)",
          fontSize: size * 0.4,
          boxShadow: "0 0 20px rgba(245, 130, 32, 0.2), 0 0 40px rgba(245, 130, 32, 0.1)",
          border: "2px solid rgba(245, 130, 32, 0.4)",
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
        style={{
          boxShadow:
            "0 0 20px rgba(245, 130, 32, 0.2), 0 0 40px rgba(245, 130, 32, 0.1)",
        }}
      />

      {/* Border ring */}
      <div
        className="absolute inset-0 rounded-full"
        style={{
          border: "2px solid rgba(245, 130, 32, 0.4)",
        }}
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
