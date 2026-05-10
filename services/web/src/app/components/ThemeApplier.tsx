"use client";

import { useEffect } from "react";
import { useTheme } from "./ThemeContext";
import { useTeam } from "./TeamContext";
import { applyTeamTheme } from "./themeTokens";

// No render output — just writes derived tokens to :root whenever the team or
// theme mode changes. Mounted inside TeamProvider so it has access to both
// contexts; runs once on mount to apply the persisted preferences.
export function ThemeApplier() {
  const { mode } = useTheme();
  const { team } = useTeam();

  useEffect(() => {
    applyTeamTheme(team, mode);
  }, [team, mode]);

  return null;
}
