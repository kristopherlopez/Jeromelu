"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

// --- Types ---

export interface ClipMeta {
  id: string;
  file: string;
  category: "idle" | "reaction" | "directional" | "micro";
  mood: string;
  duration_ms: number;
  loop: boolean;
  transitions_to: string[];
  priority: number;
}

interface Manifest {
  clips: ClipMeta[];
}

interface AvatarState {
  currentClip: ClipMeta | null;
  clipSrc: string;
  isTransitioning: boolean;
}

interface AvatarEngineContextValue {
  state: AvatarState;
  triggerClip: (category: string, mood?: string) => void;
  allClips: ClipMeta[];
}

const AvatarEngineContext = createContext<AvatarEngineContextValue | null>(null);

// --- Hook ---

export function useAvatarEngine() {
  const ctx = useContext(AvatarEngineContext);
  if (!ctx) {
    throw new Error("useAvatarEngine must be used within <AvatarEngineProvider>");
  }
  return ctx;
}

// --- Helpers ---

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function findClip(
  clips: ClipMeta[],
  category: string,
  mood?: string
): ClipMeta | null {
  // Find clips matching category + mood, fall back to category only
  const withMood = mood
    ? clips.filter((c) => c.category === category && c.mood === mood)
    : [];
  if (withMood.length > 0) return pickRandom(withMood);

  const byCategory = clips.filter((c) => c.category === category);
  if (byCategory.length > 0) return pickRandom(byCategory);

  return null;
}

function canTransition(from: ClipMeta, to: ClipMeta): boolean {
  // If no transitions defined, allow any transition (loose mode for small libraries)
  if (from.transitions_to.length === 0) return true;
  return from.transitions_to.includes(to.id);
}

function clipUrl(file: string): string {
  return `/avatar/${file}`;
}

// --- Provider ---

const IDLE_SWAP_MIN_MS = 8_000;
const IDLE_SWAP_MAX_MS = 12_000;
const MICRO_CHANCE = 0.2; // 20% chance to play a micro-expression between idles

export function AvatarEngineProvider({ children }: { children: ReactNode }) {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [state, setState] = useState<AvatarState>({
    currentClip: null,
    clipSrc: "/avatar/breathing1.mp4",
    isTransitioning: false,
  });

  const currentClipRef = useRef<ClipMeta | null>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clipEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load manifest
  useEffect(() => {
    fetch("/avatar/manifest.json", { cache: "no-store" })
      .then((r) => r.json())
      .then((m: Manifest) => {
        setManifest(m);
        // Set initial clip
        const idleClips = m.clips.filter((c) => c.category === "idle");
        const initial = idleClips.length > 0 ? pickRandom(idleClips) : m.clips[0];
        if (initial) {
          currentClipRef.current = initial;
          setState({
            currentClip: initial,
            clipSrc: clipUrl(initial.file),
            isTransitioning: false,
          });
        }
      })
      .catch(() => {
        // Manifest not available — stay on default
      });
  }, []);

  // Transition to a specific clip
  const transitionTo = useCallback(
    (clip: ClipMeta) => {
      // Clear any pending timers
      if (clipEndTimerRef.current) clearTimeout(clipEndTimerRef.current);
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);

      currentClipRef.current = clip;
      setState({
        currentClip: clip,
        clipSrc: clipUrl(clip.file),
        isTransitioning: true,
      });

      // After transition settles
      setTimeout(() => {
        setState((prev) => ({ ...prev, isTransitioning: false }));
      }, 350);

      // If non-looping, schedule return to idle after clip duration
      if (!clip.loop && manifest) {
        clipEndTimerRef.current = setTimeout(() => {
          const idleClips = manifest.clips.filter((c) => c.category === "idle");
          if (idleClips.length > 0) {
            transitionTo(pickRandom(idleClips));
          }
        }, clip.duration_ms);
      }

      // Schedule idle swap
      if (clip.loop) {
        scheduleIdleSwap();
      }
    },
    [manifest]
  );

  // Schedule next idle swap
  const scheduleIdleSwap = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    if (!manifest) return;

    const delay =
      IDLE_SWAP_MIN_MS +
      Math.random() * (IDLE_SWAP_MAX_MS - IDLE_SWAP_MIN_MS);

    idleTimerRef.current = setTimeout(() => {
      const current = currentClipRef.current;
      if (!current || current.category !== "idle") return;

      // 20% chance to play a micro-expression
      const microClips = manifest.clips.filter((c) => c.category === "micro");
      if (microClips.length > 0 && Math.random() < MICRO_CHANCE) {
        const micro = pickRandom(microClips);
        if (canTransition(current, micro)) {
          transitionTo(micro);
          return;
        }
      }

      // Swap to a different idle
      const idleClips = manifest.clips.filter(
        (c) => c.category === "idle" && c.id !== current.id
      );
      if (idleClips.length > 0) {
        transitionTo(pickRandom(idleClips));
      } else {
        // Only one idle clip — just reschedule
        scheduleIdleSwap();
      }
    }, delay);
  }, [manifest, transitionTo]);

  // Start idle cycling once manifest loads
  useEffect(() => {
    if (manifest && currentClipRef.current?.category === "idle") {
      scheduleIdleSwap();
    }
    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      if (clipEndTimerRef.current) clearTimeout(clipEndTimerRef.current);
    };
  }, [manifest, scheduleIdleSwap]);

  // Public trigger function
  const triggerClip = useCallback(
    (category: string, mood?: string) => {
      if (!manifest) return;

      const target = findClip(manifest.clips, category, mood);
      if (!target) return;

      const current = currentClipRef.current;

      // Don't interrupt higher-priority clips
      if (current && current.priority > target.priority && !current.loop) return;

      // Check if we can transition directly
      if (current && canTransition(current, target)) {
        transitionTo(target);
      } else {
        // Go through idle first, then to target
        const idleClips = manifest.clips.filter((c) => c.category === "idle");
        if (idleClips.length > 0) {
          const idle = pickRandom(idleClips);
          transitionTo(idle);
          // Queue the target after a brief idle
          setTimeout(() => {
            transitionTo(target);
          }, 500);
        } else {
          // No idle clips available, just force it
          transitionTo(target);
        }
      }
    },
    [manifest, transitionTo]
  );

  return (
    <AvatarEngineContext.Provider
      value={{
        state,
        triggerClip,
        allClips: manifest?.clips ?? [],
      }}
    >
      {children}
    </AvatarEngineContext.Provider>
  );
}
