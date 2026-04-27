export type PulseIconKey =
  | "search"
  | "pen"
  | "brain"
  | "chart"
  | "book"
  | "play"
  | "radio"
  | "doc"
  | "chat"
  | "spark";

export type CrewMember = {
  id: string;
  name: string;
  role: string;
  /** CSS variable expression, e.g. "var(--accent)" */
  color: string;
  icon: PulseIconKey;
  schedule: string;
};

export type TimelineKind = "discovered" | "processed" | "running" | "queued";

export type SourceType =
  | "video"
  | "podcast"
  | "article"
  | "tweet"
  | "stats"
  | "feed"
  | "schedule";

export type TimelineSource = {
  type: SourceType;
  title: string;
  host?: string;
  duration?: string;
  url?: string;
};

export type TimelineEntry = {
  /** Minutes relative to "now". Negative = past, 0 = current, positive = upcoming. */
  t: number;
  agent: string;
  kind: TimelineKind;
  source: TimelineSource;
  note: string;
  claims?: string[];
};

export type PulsePhase = "build-up" | "game-day" | "review";

export type PulseTeam = {
  /** 3-letter team code, e.g. "STO" */
  code: string;
  /** Short display name, e.g. "Storm" */
  name: string;
  /** CSS variable expression for the team accent, e.g. "var(--accent)" */
  color: string;
};

export type PulseFixture = {
  home: PulseTeam;
  away: PulseTeam;
  /**
   * Minutes from "now" until kickoff. Negative means already kicked off.
   * Mirrors the relative-time convention used by `TimelineEntry.t`.
   */
  kickoffMinutes: number;
  /** Pre-formatted wall-clock label, e.g. "Fri 7:50pm AEST". */
  kickoffLabel: string;
  venue: string;
};

export type PulseContext = {
  round: number;
  phase: PulsePhase;
  fixture: PulseFixture;
};

export type PulseResponse = {
  context: PulseContext;
  crew: CrewMember[];
  timeline: TimelineEntry[];
};
