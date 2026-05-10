// Team-driven theme token derivation. Mounted by ThemeApplier; rewrites the
// :root CSS custom properties whenever the selected team or theme mode changes.

import type { TeamColours } from "./teams";

export type ThemeMode = "light" | "dark";

export interface DerivedPalette {
  primary: string;
  bg: string;
  surface: string;
  border: string;
  fg: string;
  fgMuted: string;
  fgFaint: string;
  accent: string;
  accentBg: string;
  accentBorder: string;
  secondary: string;
  secondaryBg: string;
  secondaryBorder: string;
}

// ── colour utils ──
function hexToRgb(hex: string) {
  const h = hex.replace("#", "");
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}
function rgbToHex(r: number, g: number, b: number) {
  const c = (n: number) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
  return "#" + c(r) + c(g) + c(b);
}
function rgba(hex: string, a: number) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r},${g},${b},${a})`;
}
function mix(a: string, b: string, ratio: number) {
  const A = hexToRgb(a), B = hexToRgb(b);
  return rgbToHex(
    A.r * (1 - ratio) + B.r * ratio,
    A.g * (1 - ratio) + B.g * ratio,
    A.b * (1 - ratio) + B.b * ratio,
  );
}
function luminance(hex: string) {
  const { r, g, b } = hexToRgb(hex);
  const norm = (v: number) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * norm(r) + 0.7152 * norm(g) + 0.0722 * norm(b);
}
function ensureContrastingAccent(accent: string, bgIsDark: boolean) {
  const lum = luminance(accent);
  if (bgIsDark && lum < 0.18) return mix(accent, "#ffffff", 0.45);
  if (!bgIsDark && lum > 0.78) return mix(accent, "#000000", 0.35);
  return accent;
}

// Pick the colour with the strongest "personality" (highest chroma, mid luminance).
// Black/white/grey lose to a saturated colour — so Wests Tigers (black + orange)
// gets orange as the accent rather than black.
function pickAccentSource(primary: string, secondary: string) {
  const score = (hex: string) => {
    const { r, g, b } = hexToRgb(hex);
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const chroma = max - min;
    const lum = luminance(hex);
    const lumPenalty = lum < 0.05 || lum > 0.92 ? -120 : 0;
    return chroma + lumPenalty;
  };
  return score(secondary) > score(primary) ? secondary : primary;
}

export function derive(team: TeamColours, mode: ThemeMode): DerivedPalette {
  const primary = team.primary;
  const secondary = team.secondary;
  const accentSource = pickAccentSource(primary, secondary);
  const secSource = accentSource === primary ? secondary : primary;

  if (mode === "light") {
    const accent = ensureContrastingAccent(accentSource, false);
    // If the secondary source is white, derive a tinted variant so secondary
    // chips don't disappear against the surface.
    const secAccent = luminance(secSource) > 0.85
      ? ensureContrastingAccent(mix(accentSource, "#000000", 0.45), false)
      : ensureContrastingAccent(secSource, false);
    return {
      primary,
      bg:               mix("#FAF9F5", accent, 0.04),
      surface:          "#FFFFFF",
      border:           rgba(accent, 0.14),
      fg:               "#1C1A14",
      fgMuted:          "#5C544A",
      fgFaint:          "#9B9384",
      accent,
      accentBg:         rgba(accent, 0.10),
      accentBorder:     rgba(accent, 0.32),
      secondary:        secAccent,
      secondaryBg:      rgba(secAccent, 0.10),
      secondaryBorder:  rgba(secAccent, 0.28),
    };
  }

  // Dark / Away — warm-earth dark surfaces tinted by accent source
  const accent = ensureContrastingAccent(accentSource, true);
  const secAccent = luminance(secSource) > 0.85
    ? ensureContrastingAccent(mix(accentSource, "#FFFFFF", 0.55), true)
    : ensureContrastingAccent(secSource, true);
  return {
    primary,
    bg:               mix("#241E1A", accent, 0.08),
    surface:          mix("#342C26", accent, 0.06),
    border:           rgba(accent, 0.22),
    fg:               "#EDE4D6",
    fgMuted:          "#948878",
    fgFaint:          "#6E6458",
    accent,
    accentBg:         rgba(accent, 0.12),
    accentBorder:     rgba(accent, 0.28),
    secondary:        secAccent,
    secondaryBg:      rgba(secAccent, 0.12),
    secondaryBorder:  rgba(secAccent, 0.28),
  };
}

// ── apply derived palettes to :root ──
//
// We always write BOTH the light-mode wiki tokens AND the dark base tokens,
// because different code paths read from different sets:
//   - light mode: wiki.css's `[data-theme="light"]` block reads `--wiki-*`
//   - dark mode:  the dark block aliases `--wiki-*` to `--background`/`--accent`
//                 etc., and the topbar reads `--accent`/`--background-deep`/...
//
// The current-mode accent is also written to the legacy alias tokens
// (`--terracotta`, `--tigers-orange`) so any component still referencing those
// stays in sync.
export function applyTeamTheme(team: TeamColours, mode: ThemeMode) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const light = derive(team, "light");
  const dark = derive(team, "dark");
  const current = mode === "light" ? light : dark;

  // Wiki light-mode tokens (used when .wiki-page has data-theme="light")
  root.style.setProperty("--wiki-bg",            light.bg);
  root.style.setProperty("--wiki-surface",       light.surface);
  root.style.setProperty("--wiki-border",        light.border);
  root.style.setProperty("--wiki-border-strong", rgba(light.accent, 0.22));
  root.style.setProperty("--wiki-ink",           light.fg);
  root.style.setProperty("--wiki-ink-muted",     light.fgMuted);
  root.style.setProperty("--wiki-ink-faint",     light.fgFaint);
  root.style.setProperty("--wiki-accent",        light.accent);
  root.style.setProperty("--wiki-accent-bg",     light.accentBg);
  root.style.setProperty("--wiki-nav-bg",        rgba(light.bg, 0.93));

  // Dark base tokens (used directly in dark mode, also aliased by wiki dark)
  root.style.setProperty("--background",            dark.bg);
  root.style.setProperty("--background-deep",       mix(dark.bg, "#000000", 0.10));
  root.style.setProperty("--surface",               dark.surface);
  root.style.setProperty("--surface-hover",         mix(dark.surface, "#FFFFFF", 0.06));
  root.style.setProperty("--border",                dark.border);
  root.style.setProperty("--border-subtle",         rgba(dark.accent, 0.14));
  root.style.setProperty("--foreground",            dark.fg);
  root.style.setProperty("--foreground-secondary",  mix(dark.fg, dark.fgMuted, 0.4));
  root.style.setProperty("--foreground-muted",      dark.fgMuted);
  root.style.setProperty("--foreground-faint",      dark.fgFaint);
  root.style.setProperty("--foreground-ghost",      mix(dark.fgFaint, dark.bg, 0.4));

  // Current-mode accent — drives the topbar pills, ring pulses, focus glows,
  // and any component still using the legacy --tigers-orange/--terracotta.
  root.style.setProperty("--accent",              current.accent);
  root.style.setProperty("--accent-bg",           current.accentBg);
  root.style.setProperty("--accent-border",       current.accentBorder);
  root.style.setProperty("--accent-glow",         rgba(current.accent, 0.35));
  root.style.setProperty("--terracotta",          current.accent);
  root.style.setProperty("--terracotta-bg",       current.accentBg);
  root.style.setProperty("--tigers-orange",       current.accent);
  root.style.setProperty("--tigers-orange-glow",  rgba(current.accent, 0.35));
}
