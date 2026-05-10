"use client";

import { useEffect, useState } from "react";
import { extractVideoId } from "./youtube";

// YouTube serves `oar2.jpg` ("original aspect ratio") at the source's native
// aspect: ~16:9 for regular uploads, ~9:16 for Shorts. The `*default.jpg`
// variants are all letterboxed into a fixed landscape frame so they can't
// distinguish a Short. `oar2.jpg` 404s on some old videos; we treat that as
// not-a-Short, which is correct in practice.

const cache = new Map<string, boolean>();

export function useIsYouTubeShort(videoUrl: string | null | undefined): boolean {
  const videoId = extractVideoId(videoUrl);
  const [isShort, setIsShort] = useState<boolean>(() =>
    videoId ? (cache.get(videoId) ?? false) : false,
  );

  useEffect(() => {
    if (!videoId) return;
    if (cache.has(videoId)) return;
    const img = new Image();
    let cancelled = false;
    img.onload = () => {
      if (cancelled) return;
      const portrait = img.naturalHeight > img.naturalWidth;
      cache.set(videoId, portrait);
      setIsShort(portrait);
    };
    img.onerror = () => {
      if (cancelled) return;
      cache.set(videoId, false);
    };
    img.src = `https://i.ytimg.com/vi/${videoId}/oar2.jpg`;
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  return isShort;
}
