"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

type ThemeMode = "light" | "dark";

interface ThemeState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  /** Resolved boolean — true = light/parchment, false = dark */
  isLight: boolean;
}

const STORAGE_KEY = "jaromelu-theme";
const DEFAULT_MODE: ThemeMode = "dark";

const ThemeContext = createContext<ThemeState>({
  mode: DEFAULT_MODE,
  setMode: () => {},
  isLight: false,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(DEFAULT_MODE);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "light" || stored === "dark") {
        setModeState(stored);
      }
    } catch {}
  }, []);

  const setMode = (next: ThemeMode) => {
    setModeState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch {}
  };

  const isLight = mode === "light";

  return (
    <ThemeContext.Provider value={{ mode, setMode, isLight }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
