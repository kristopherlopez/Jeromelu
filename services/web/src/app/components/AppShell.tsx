"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AvatarEngineProvider } from "./AvatarEngine";
import { JeromeluPresence } from "./JeromeluPresence";
import { JeromeluTopBar, TOPBAR_HEIGHT } from "./JeromeluTopBar";
import { ThemeProvider, useTheme } from "./ThemeContext";
import { TeamProvider } from "./TeamContext";
import { ThemeApplier } from "./ThemeApplier";
import { TransitionProvider, CONTENT_DELAY_MS, CONTENT_FADE_MS } from "./TransitionContext";

function PageContent({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const prevPathnameRef = useRef(pathname);
  const phaseRef = useRef<"visible" | "hidden" | "fading-in">("visible");
  const [, tick] = useState(0);
  const rerender = () => tick((n) => n + 1);

  // Detect route change synchronously during render — no flash
  if (prevPathnameRef.current !== pathname) {
    const wasHome = prevPathnameRef.current === "/landing";
    const nowHome = pathname === "/landing";
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

  const { isLight } = useTheme();

  // Reserve room for the top bar on every page where JeromeluTopBar renders.
  // Mirrors the exclusion list in JeromeluTopBar.
  const hasTopBar =
    pathname !== "/landing" &&
    !pathname.startsWith("/admin") &&
    !pathname.startsWith("/wiki/source");

  return (
    <div
      className="wiki-page"
      data-theme={isLight ? "light" : "dark"}
      style={{
        opacity,
        transition,
        minHeight: "100vh",
        paddingTop: hasTopBar ? TOPBAR_HEIGHT : 0,
        backgroundColor: isLight ? "var(--wiki-bg, #FAF9F5)" : "var(--background)",
        color: isLight ? "var(--wiki-ink, #1c1a14)" : "var(--foreground)",
      }}
    >
      {children}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <TeamProvider>
        <ThemeApplier />
        <AvatarEngineProvider>
          <TransitionProvider>
            <JeromeluPresence />
            <JeromeluTopBar />
            <PageContent>{children}</PageContent>
          </TransitionProvider>
        </AvatarEngineProvider>
      </TeamProvider>
    </ThemeProvider>
  );
}
