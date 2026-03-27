"use client";

import { createContext, useContext, useState, useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

export const TRANSITION_DURATION_MS = 900;
// Content starts fading in while the avatar is still decelerating
export const CONTENT_DELAY_MS = 550;
export const CONTENT_FADE_MS = 500;

interface TransitionContextValue {
  isTransitioning: boolean;
  isHome: boolean;
}

const TransitionContext = createContext<TransitionContextValue>({
  isTransitioning: false,
  isHome: true,
});

export const usePageTransition = () => useContext(TransitionContext);

export function TransitionProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isHome = pathname === "/";
  const prevIsHomeRef = useRef(isHome);
  const transitioningRef = useRef(false);
  const [tick, setTick] = useState(0);

  // Set ref synchronously during render — no flash
  if (prevIsHomeRef.current !== isHome) {
    prevIsHomeRef.current = isHome;
    transitioningRef.current = true;
  }

  // Clear the flag after the animation completes, then force re-render
  useEffect(() => {
    if (transitioningRef.current) {
      const timer = setTimeout(() => {
        transitioningRef.current = false;
        setTick((n) => n + 1);
      }, TRANSITION_DURATION_MS);
      return () => clearTimeout(timer);
    }
  }, [isHome]);

  return (
    <TransitionContext.Provider value={{ isTransitioning: transitioningRef.current, isHome }}>
      {children}
    </TransitionContext.Provider>
  );
}
