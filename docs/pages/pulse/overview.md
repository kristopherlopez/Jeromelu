# Live Pulse

Status: **Stub — UI ported from design artifact, data is mock**

---

## Summary

Live Pulse is the "Morning, coach" home view: a page-context strip up top (current NRL round, phase of the week, marquee fixture and kickoff countdown), a compact strip showing what the crew is doing right now, a feed of fresh discoveries/processings, and a right-rail crew status block. It's the answer to *"what's been happening while I was away?"*

Route: `/pulse`
Code: `services/web/src/app/pulse/`
API stub: `services/web/src/app/api/pulse/route.ts` (Next.js route handler — returns mock `crew` + `timeline`)

The design originated in `design-artifacts/claude-design/Jaromelu Scheduled.html` (the "Live Pulse" mode of the Scheduled-run concept). This page integrates that mode into the main app as a standalone surface.

---

## Files

| File | Purpose |
|------|---------|
| `services/web/src/app/pulse/page.tsx` | Server entry. SSR-fetches `/api/pulse` so the first paint has content. |
| `services/web/src/app/pulse/PulseClient.tsx` | Client component. Renders the strip, feed, and crew rail. Polls `/api/pulse` every 30s. |
| `services/web/src/app/pulse/pulse-data.ts` | Shared types (`PulseResponse`, `CrewMember`, `TimelineEntry`, …). |
| `services/web/src/app/api/pulse/route.ts` | Stub API. Returns `{ crew, timeline }` — to be replaced with real data from runs/discoveries tables. |

Top bar: a "Live Pulse" entry lives in `NAV_ITEMS` in `services/web/src/app/components/JeromeluTopBar.tsx` — the global top bar that renders on every inner page (everything except `/landing`, `/admin/*`, `/stream/*`). The entry is intentionally *not* part of the JAROMELU logo letters (`LETTERS` in `JeromeluLogo.tsx`), so adding it does not change the logo.

`JeromeluTopBar` is a fixed 56px bar at the top of the viewport. Content clearance is handled centrally in `AppShell.tsx` (`paddingTop: TOPBAR_HEIGHT` on the `PageContent` wrapper when `hasTopBar` is true), so individual pages don't have to add their own offset. The bar's background tracks the active theme — `--background-deep` on dark, `--wiki-surface` on light.

Pulse uses the theme-aware `--wiki-*` token family (`--wiki-surface`, `--wiki-border`, `--wiki-ink`, `--wiki-ink-muted`, `--wiki-ink-faint`, `--wiki-accent`, `--wiki-accent-bg`) defined in `services/web/src/app/wiki/wiki.css`. These are scoped to the `.wiki-page[data-theme="light|dark"]` wrapper that `AppShell` puts around every page, so flipping the global theme also flips the Pulse cards. Don't reach for `--background-deep` / `--foreground-*` directly here — they're dark-only and will render as black boxes / invisible text on light theme.

---

## Data shape

`GET /api/pulse` returns:

```ts
type PulseResponse = {
  context: PulseContext;     // round, phase, marquee fixture
  crew: CrewMember[];        // 5 named agents (Scout, Scribe, Analyst, Stats, Fixtures)
  timeline: TimelineEntry[]; // ordered by `t`, ascending
};

type PulseContext = {
  round: number;             // current NRL round
  phase: "build-up" | "game-day" | "review";
  fixture: {
    home: { code: string; name: string; color: string };
    away: { code: string; name: string; color: string };
    kickoffMinutes: number;  // minutes from "now"; negative = already kicked off
    kickoffLabel: string;    // pre-formatted wall clock, e.g. "Fri 7:50pm AEST"
    venue: string;
  };
};

type TimelineEntry = {
  t: number;          // minutes relative to "now" (negative = past, 0 = now, positive = upcoming)
  agent: string;      // crew member id
  kind: "discovered" | "processed" | "running" | "queued";
  source: { type: SourceType; title: string; host?: string; duration?: string; url?: string };
  note: string;
  claims?: string[];  // up to N example claims, surfaced under the item
};
```

`t` and `kickoffMinutes` are **relative**, not absolute, so the stub stays evergreen without pinning a date. When real data lands, the API can either keep returning relative offsets computed server-side, or switch to absolute timestamps and translate on the client.

---

## Open work

- **Real data** — replace the stub with queries against the runs / discoveries tables (likely sourced from Temporal workflows). Per-agent status, last-N events, currently running tasks.
- **Live updates** — polling at 30s is fine for a stub. Upgrade to SSE or WebSocket once the backing tables are live.
- **Animation** — the design has a `tick` heartbeat that fades in items one-by-one. We deliberately omitted this; revisit if the page feels static once real data is flowing.
- **Mobile layout** — the right rail collapses on `<lg`. Crew status currently disappears on small screens; decide whether it becomes a top strip, a bottom sheet, or stays hidden.

---

## Related

- [docs/pages/feed/overview.md](../feed/overview.md) — adjacent surface, "what's happening" focused
- [docs/architecture/03-experience-architecture.md](../../architecture/03-experience-architecture.md)
- [design-artifacts/claude-design/Jaromelu Scheduled.html](../../../design-artifacts/claude-design/) — the design source (Pulse is the first of four modes there)
