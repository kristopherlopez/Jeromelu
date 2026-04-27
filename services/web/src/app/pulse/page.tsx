import { headers } from "next/headers";
import PulseClient from "./PulseClient";
import type { PulseResponse } from "./pulse-data";

export const metadata = {
  title: "Live Pulse | Jaromelu",
  description: "Morning, coach. Here's what the crew has been up to.",
};

// Stub data is served by /api/pulse on the same host. We hit it during SSR so the
// first paint already has content; the client re-polls for updates.
async function loadPulse(): Promise<PulseResponse> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  const proto = h.get("x-forwarded-proto") ?? "http";
  const url = host ? `${proto}://${host}/api/pulse` : "/api/pulse";
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    return {
      context: {
        round: 0,
        phase: "build-up",
        fixture: {
          home: { code: "—", name: "—", color: "var(--wiki-ink-faint)" },
          away: { code: "—", name: "—", color: "var(--wiki-ink-faint)" },
          kickoffMinutes: 0,
          kickoffLabel: "—",
          venue: "—",
        },
      },
      crew: [],
      timeline: [],
    };
  }
  return res.json();
}

export default async function PulsePage() {
  const initial = await loadPulse();
  return <PulseClient initial={initial} />;
}
