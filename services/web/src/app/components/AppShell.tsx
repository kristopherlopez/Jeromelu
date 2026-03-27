"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AvatarEngineProvider } from "./AvatarEngine";
import { JeromeluPresence } from "./JeromeluPresence";
import { TransitionProvider, CONTENT_DELAY_MS, CONTENT_FADE_MS } from "./TransitionContext";

function PageContent({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const prevPathnameRef = useRef(pathname);
  const phaseRef = useRef<"visible" | "hidden" | "fading-in">("visible");
  const [, tick] = useState(0);
  const rerender = () => tick((n) => n + 1);

  // Detect route change synchronously during render — no flash
  if (prevPathnameRef.current !== pathname) {
    const wasHome = prevPathnameRef.current === "/";
    const nowHome = pathname === "/";
    prevPathnameRef.current = pathname;
    if (wasHome !== nowHome) {
      phaseRef.current = "hidden";
    }
  }

  // Schedule fade-in after the avatar transition settles
  useEffect(() => {
    if (phaseRef.current !== "hidden") return;
    const t1 = setTimeout(() => {
      phaseRef.current = "fading-in";
      rerender();
    }, CONTENT_DELAY_MS);
    const t2 = setTimeout(() => {
      phaseRef.current = "visible";
      rerender();
    }, CONTENT_DELAY_MS + CONTENT_FADE_MS);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [pathname]);

  const phase = phaseRef.current;
  const opacity = phase === "visible" || phase === "fading-in" ? 1 : 0;
  const transition =
    phase === "fading-in"
      ? `opacity ${CONTENT_FADE_MS}ms ease-in`
      : "none";

  return (
    <div style={{ opacity, transition }}>
      {children}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <AvatarEngineProvider>
      <TransitionProvider>
        <JeromeluPresence />
        <PageContent>{children}</PageContent>
      </TransitionProvider>
    </AvatarEngineProvider>
  );
}
