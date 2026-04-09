"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { usePathname } from "next/navigation";

type ThemeMode = "auto" | "light" | "dark";

interface ThemeState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  /** Resolved boolean — true = light/parchment, false = dark */
  isLight: boolean;
}

const STORAGE_KEY = "jaromelu-theme";

/** Routes that default to light theme when mode is 'auto' */
const LIGHT_PREFIX_ROUTES = ["/wiki", "/feed"];

const ThemeContext = createContext<ThemeState>({
  mode: "auto",
  setMode: () => {},
  isLight: false,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mode, setModeState] = useState<ThemeMode>("auto");

  // Read persisted preference on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
      if (stored === "light" || stored === "dark" || stored === "auto") {
        setModeState(stored);
      }
    } catch {}
  }, []);

  const setMode = (next: ThemeMode) => {
    setModeState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch {}
  };

  // Resolve final isLight
  let isLight: boolean;
  if (mode === "light") {
    isLight = true;
  } else if (mode === "dark") {
    isLight = false;
  } else {
    // auto — route-based
    isLight = pathname === "/" || LIGHT_PREFIX_ROUTES.some((r) => pathname.startsWith(r));
  }

  return (
    <ThemeContext.Provider value={{ mode, setMode, isLight }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
