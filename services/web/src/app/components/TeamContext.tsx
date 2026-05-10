"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { DEFAULT_TEAM_SLUG, TEAM_BY_SLUG, getTeam, type TeamColours } from "./teams";

interface TeamState {
  slug: string;
  team: TeamColours;
  setTeam: (slug: string) => void;
}

const STORAGE_KEY = "jaromelu-team";

const ThemeContext = createContext<TeamState>({
  slug: DEFAULT_TEAM_SLUG,
  team: getTeam(DEFAULT_TEAM_SLUG),
  setTeam: () => {},
});

export function TeamProvider({ children }: { children: ReactNode }) {
  const [slug, setSlug] = useState<string>(DEFAULT_TEAM_SLUG);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && TEAM_BY_SLUG[stored]) setSlug(stored);
    } catch {}
  }, []);

  const setTeam = (next: string) => {
    if (!TEAM_BY_SLUG[next]) return;
    setSlug(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch {}
  };

  return (
    <ThemeContext.Provider value={{ slug, team: getTeam(slug), setTeam }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTeam() {
  return useContext(ThemeContext);
}
