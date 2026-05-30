import { NextResponse } from "next/server";
import type { PulseResponse } from "@/app/pulse/pulse-data";

/**
 * Stubbed crew + timeline data for the /pulse view.
 *
 * `t` is **minutes relative to "now"** — negative = past, 0 = right now, positive = upcoming.
 * The client computes labels at render time, so this stays evergreen without us pinning a date.
 *
 * Replace with real data sourced from the runs/discoveries tables once the pipeline lands.
 */

const CONTEXT: PulseResponse["context"] = {
  round: 7,
  phase: "build-up",
  fixture: {
    home: { code: "STO", name: "Storm", color: "var(--teal)" },
    away: { code: "ROO", name: "Roosters", color: "var(--terracotta)" },
    // ~2d 08h from "now"
    kickoffMinutes: 60 * 56,
    kickoffLabel: "Fri 7:50pm AEST",
    venue: "AAMI Park",
  },
};

const CREW: PulseResponse["crew"] = [
  { id: "miner", name: "Miner", role: "finds new sources", color: "var(--accent)", icon: "search", schedule: "Every 4h" },
  { id: "scribe", name: "Scribe", role: "transcribes audio/video", color: "var(--terracotta)", icon: "pen", schedule: "When Miner finds new" },
  { id: "analyst", name: "Analyst", role: "extracts claims", color: "var(--lilac)", icon: "brain", schedule: "After Scribe" },
  { id: "stats", name: "Stats", role: "pulls numbers", color: "var(--teal)", icon: "chart", schedule: "Mon 6AM" },
  { id: "fixtures", name: "Fixtures", role: "tracks team news", color: "var(--ochre)", icon: "book", schedule: "Thu 6PM" },
];

const TIMELINE: PulseResponse["timeline"] = [
  // ~6h ago — Miner's overnight run
  { t: -370, agent: "miner", kind: "discovered", source: { type: "video", title: "Tigers vs Panthers — Full Match Replay", host: "NRL on Nine", url: "youtube.com/...", duration: "1:42:18" }, note: "Friday's full game just dropped." },
  { t: -368, agent: "miner", kind: "discovered", source: { type: "podcast", title: "Sin Bin Ep. 412 — Round 7 Reset", host: "Andrew Johns + Brandy", duration: "58:12" }, note: "Joey & Brandy talking halves." },
  { t: -365, agent: "miner", kind: "discovered", source: { type: "article", title: "Luai's quiet brilliance papers over Tigers cracks", host: "Wide World of Sports" }, note: "Long read on Tigers' midfield." },
  { t: -340, agent: "scribe", kind: "processed", source: { type: "video", title: "Tigers vs Panthers" }, note: "Transcript ready · 1,847 lines." },
  { t: -310, agent: "scribe", kind: "processed", source: { type: "podcast", title: "Sin Bin Ep. 412" }, note: "Transcript ready · 642 lines." },
  {
    t: -280, agent: "analyst", kind: "processed",
    source: { type: "podcast", title: "Sin Bin Ep. 412" },
    note: "Extracted 7 claims · 3 about Luai.",
    claims: [
      "Joey: 'Luai's the best he's been in 2 years'",
      "Brandy: 'Tigers fixture Rd 7-9 is forgiving'",
      "Joey: 'Don't trade Cleary for him though'",
    ],
  },

  // ~4h ago
  { t: -240, agent: "fixtures", kind: "discovered", source: { type: "tweet", title: "Late mail: Galvin in doubt", host: "@TheMole_NRL" }, note: "Hamstring tightness Friday training." },
  { t: -220, agent: "miner", kind: "discovered", source: { type: "article", title: "Bunnies sweat on Walker fitness", host: "Sydney Morning Herald" }, note: "Grade 1 calf — game-day call." },
  {
    t: -180, agent: "analyst", kind: "processed",
    source: { type: "article", title: "Luai's quiet brilliance" },
    note: "Extracted 4 claims · cross-checked Ledger.",
    claims: [
      "Tigers structure has shifted post-Round 5",
      "Luai-Doueihi combination averaging 12 line-break assists",
    ],
  },

  // ~2h ago
  { t: -150, agent: "stats", kind: "processed", source: { type: "stats", title: "Round 7 SuperCoach prices refreshed" }, note: "1,247 player rows updated." },

  // ~30m ago
  { t: -28, agent: "miner", kind: "discovered", source: { type: "video", title: "Tedesco try clip — Roosters trial", host: "Fox League" }, note: "Worth a look. Looks fit." },
  { t: -22, agent: "miner", kind: "discovered", source: { type: "tweet", title: "Storm name 18-man squad", host: "@storm" }, note: "Hughes named, Munster benched? Cap call." },

  // Now — running
  { t: -2, agent: "miner", kind: "running", source: { type: "feed", title: "Scanning Reddit r/nrl" }, note: "Looking for late mail." },
  { t: -1, agent: "scribe", kind: "running", source: { type: "podcast", title: "NRL360 — Friday Show" }, note: "Transcribing · 38% done." },

  // Queued / upcoming
  { t: 0, agent: "analyst", kind: "queued", source: { type: "podcast", title: "NRL360" }, note: "Waits for Scribe." },
  { t: 60, agent: "miner", kind: "queued", source: { type: "schedule", title: "Next sweep" }, note: "Round 7 team list deadline." },
  { t: 720, agent: "fixtures", kind: "queued", source: { type: "schedule", title: "Thursday team-list scan" }, note: "Cron · Thu 6PM." },
];

export async function GET() {
  const body: PulseResponse = { context: CONTEXT, crew: CREW, timeline: TIMELINE };
  return NextResponse.json(body);
}
