"use client";

import { useState, useMemo } from "react";
import type {
  LedgerResponse,
  PredictionStatus,
  PredictionCategory,
  PredictorKind,
  ScoreboardEntry,
  Prediction,
  HotZone,
  CategoryBreakdown,
} from "./ledger-data";
import { CATEGORY_LABELS, KIND_LABELS } from "./ledger-data";

/* ── Helpers ── */

type TabKey = "scoreboard" | "predictions" | "categories";
type StatusFilter = "all" | PredictionStatus;
type CategoryFilter = "all" | PredictionCategory;

const KIND_COLORS: Record<PredictorKind, { bg: string; color: string; border: string }> = {
  ai: { bg: "var(--accent-bg)", color: "var(--accent)", border: "var(--accent-border)" },
  expert: { bg: "var(--teal-bg)", color: "var(--teal)", border: "var(--teal-border)" },
  podcast: { bg: "var(--lilac-bg)", color: "var(--lilac)", border: "rgba(168,152,200,0.22)" },
  community: { bg: "var(--slate-bg)", color: "var(--slate)", border: "rgba(138,173,204,0.22)" },
};

function KindTag({ kind }: { kind: PredictorKind }) {
  const c = KIND_COLORS[kind];
  return (
    <span
      style={{
        display: "inline-block", fontSize: "10px", fontWeight: 600,
        textTransform: "uppercase", letterSpacing: "0.04em",
        padding: "0.15rem 0.5rem", borderRadius: "3px",
        background: c.bg, color: c.color, border: `1px solid ${c.border}`,
        verticalAlign: "middle", marginLeft: "0.5rem",
      }}
    >
      {KIND_LABELS[kind]}
    </span>
  );
}

function AccuracyBar({ pct }: { pct: number }) {
  const tier = pct >= 65 ? "high" : pct >= 55 ? "mid" : "low";
  const colors = { high: "var(--teal)", mid: "var(--ochre)", low: "var(--red)" };
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
      <div style={{ width: 80, height: 6, background: "rgba(237,228,214,0.14)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: colors[tier] }} />
      </div>
      <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 13, fontWeight: 500, color: colors[tier], minWidth: "3rem" }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="transition-colors"
      style={{
        padding: "0.35rem 0.85rem", fontSize: 13, fontWeight: 500,
        color: active ? "var(--accent)" : "var(--foreground-muted)",
        background: active ? "var(--accent-bg)" : "var(--surface)",
        border: `1px solid ${active ? "var(--accent-border)" : "var(--border)"}`,
        borderRadius: 4, cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

/* ── Scoreboard Tab ── */

function ScoreboardTab({ scoreboard, hotZones }: { scoreboard: ScoreboardEntry[]; hotZones: HotZone[] }) {
  const [catFilter, setCatFilter] = useState<CategoryFilter>("all");

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        <FilterButton label="Overall" active={catFilter === "all"} onClick={() => setCatFilter("all")} />
        {(Object.keys(CATEGORY_LABELS) as PredictionCategory[]).map((cat) => (
          <FilterButton key={cat} label={CATEGORY_LABELS[cat]} active={catFilter === cat} onClick={() => setCatFilter(cat)} />
        ))}
      </div>

      {/* Table */}
      <div style={{ border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["#", "Predictor", "Accuracy", "Streak", "Calls", "Trend"].map((h, i) => (
                <th
                  key={h}
                  style={{
                    background: "var(--background-deep, #241e1a)", padding: "0.75rem 1rem",
                    fontSize: 11, fontWeight: 600, color: "var(--foreground-muted)",
                    textTransform: "uppercase", letterSpacing: "0.06em",
                    textAlign: i === 0 || i >= 3 ? "center" : "left",
                    borderBottom: "1px solid rgba(237,228,214,0.14)",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scoreboard.map((entry, i) => {
              const rank = i + 1;
              const rankColor = rank === 1 ? "var(--ochre)" : rank === 2 ? "var(--foreground-secondary)" : rank === 3 ? "var(--accent)" : "var(--foreground-muted)";
              const isJaromelu = entry.predictor.id === "jaromelu";
              const streakColors = { hot: "var(--teal)", cold: "var(--red)", neutral: "var(--foreground-muted)" };
              const trendSymbols = { up: "▲", down: "▼", flat: "—" };
              const trendColors = { up: "var(--teal)", down: "var(--red)", flat: "var(--foreground-faint)" };

              return (
                <tr key={entry.predictor.id} style={{ background: isJaromelu ? "var(--accent-bg)" : undefined }}>
                  <td style={{ padding: "0.75rem 1rem", textAlign: "center", background: isJaromelu ? undefined : "var(--surface)", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: "var(--font-geist-mono)", fontWeight: 600, fontSize: 13, color: rankColor }}>{rank}</span>
                  </td>
                  <td style={{ padding: "0.75rem 1rem", background: isJaromelu ? undefined : "var(--surface)", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontWeight: 500, color: "var(--foreground)" }}>{entry.predictor.name}</span>
                    <KindTag kind={entry.predictor.kind} />
                  </td>
                  <td style={{ padding: "0.75rem 1rem", background: isJaromelu ? undefined : "var(--surface)", borderBottom: "1px solid var(--border)" }}>
                    <AccuracyBar pct={entry.accuracy} />
                  </td>
                  <td style={{ padding: "0.75rem 1rem", textAlign: "center", background: isJaromelu ? undefined : "var(--surface)", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 13, color: streakColors[entry.streakType] }}>{entry.streak}</span>
                  </td>
                  <td style={{ padding: "0.75rem 1rem", textAlign: "center", background: isJaromelu ? undefined : "var(--surface)", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 13, color: "var(--foreground-secondary)" }}>{entry.totalCalls}</span>
                  </td>
                  <td style={{ padding: "0.75rem 1rem", textAlign: "center", background: isJaromelu ? undefined : "var(--surface)", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontSize: 11, color: trendColors[entry.trend] }}>{trendSymbols[entry.trend]}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Hot Zones */}
      <div className="mt-7">
        <div className="flex items-baseline gap-3 mb-3">
          <h3 style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "1.15rem", fontWeight: 700, color: "var(--foreground)" }}>
            Hot Zones
          </h3>
          <span style={{ fontSize: 12, color: "var(--foreground-faint)" }}>
            Pockets of unusually strong predictions — even from low-ranked sources
          </span>
        </div>
        <div
          style={{
            display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1px",
            background: "var(--border)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden",
          }}
        >
          {hotZones.map((hz, i) => {
            const deltaColor = hz.overallDelta >= 20 ? "var(--teal)" : "var(--ochre)";
            return (
              <div key={i} style={{ background: "var(--surface)", padding: "1rem 1.15rem", position: "relative" }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--foreground-secondary)", marginBottom: "0.35rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  {hz.predictor.name} <KindTag kind={hz.predictor.kind} />
                </div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--foreground)", marginBottom: "0.5rem", lineHeight: 1.3 }}>
                  {hz.scope}
                </div>
                <div style={{ display: "flex", gap: "1rem", alignItems: "baseline" }}>
                  <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: "1.25rem", fontWeight: 600, color: deltaColor }}>
                    {hz.accuracy.toFixed(1)}%
                  </span>
                  <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 11, color: deltaColor }}>
                    +{hz.overallDelta.toFixed(1)} vs overall
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "var(--foreground-faint)" }}>
                  {hz.calls} calls · {hz.correct} correct
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── Predictions Tab ── */

function PredictionsTab({ predictions }: { predictions: Prediction[] }) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [catFilter, setCatFilter] = useState<CategoryFilter>("all");

  const filtered = useMemo(() => {
    return predictions.filter((p) => {
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      if (catFilter !== "all" && p.category !== catFilter) return false;
      return true;
    });
  }, [predictions, statusFilter, catFilter]);

  const statusIcon: Record<PredictionStatus, { symbol: string; cls: string; bg: string; border: string; color: string }> = {
    correct: { symbol: "✓", cls: "status-correct", bg: "var(--teal-bg)", border: "var(--teal-border)", color: "var(--teal)" },
    wrong: { symbol: "✗", cls: "status-wrong", bg: "var(--red-bg)", border: "var(--red-border)", color: "var(--red)" },
    pending: { symbol: "⏳", cls: "status-pending", bg: "var(--ochre-bg)", border: "var(--ochre-border)", color: "var(--ochre)" },
  };

  const confColors = { high: "var(--accent)", med: "var(--ochre)", low: "var(--foreground-muted)" };

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        <FilterButton label="All" active={statusFilter === "all"} onClick={() => setStatusFilter("all")} />
        <FilterButton label="✓ Correct" active={statusFilter === "correct"} onClick={() => setStatusFilter("correct")} />
        <FilterButton label="✗ Wrong" active={statusFilter === "wrong"} onClick={() => setStatusFilter("wrong")} />
        <FilterButton label="⏳ Pending" active={statusFilter === "pending"} onClick={() => setStatusFilter("pending")} />
        <div style={{ width: 1, background: "rgba(237,228,214,0.14)", alignSelf: "stretch", margin: "0 0.25rem" }} />
        {(Object.keys(CATEGORY_LABELS) as PredictionCategory[]).map((cat) => (
          <FilterButton key={cat} label={CATEGORY_LABELS[cat]} active={catFilter === cat} onClick={() => setCatFilter(cat)} />
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 1, background: "var(--border)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
        {filtered.length === 0 ? (
          <div style={{ background: "var(--surface)", padding: "3rem", textAlign: "center", fontSize: 14, color: "var(--foreground-muted)" }}>
            No predictions match those filters.
          </div>
        ) : (
          filtered.map((p) => {
            const s = statusIcon[p.status];
            return (
              <div
                key={p.id}
                style={{
                  background: "var(--surface)", padding: "1rem 1.25rem",
                  display: "grid", gridTemplateColumns: "auto 1fr auto",
                  gap: "1rem", alignItems: "start",
                }}
              >
                {/* Status icon */}
                <div
                  style={{
                    width: 32, height: 32, borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 14, fontWeight: 600, flexShrink: 0, marginTop: "0.15rem",
                    background: s.bg, color: s.color, border: `1px solid ${s.border}`,
                  }}
                >
                  {s.symbol}
                </div>

                {/* Body */}
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: "var(--foreground)", marginBottom: "0.3rem", lineHeight: 1.4 }}>
                    {p.text}
                  </div>
                  <div className="flex flex-wrap gap-3" style={{ fontSize: 12, color: "var(--foreground-muted)" }}>
                    <span style={{ fontWeight: 500, color: "var(--foreground-secondary)" }}>{p.predictor.name}</span>
                    <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 11 }}>{p.round} · {new Date(p.timestamp).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })}</span>
                    <span style={{ fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.04em", padding: "0.1rem 0.4rem", borderRadius: 3, background: "var(--border)", color: "var(--foreground-muted)" }}>
                      {CATEGORY_LABELS[p.category]}
                    </span>
                  </div>
                </div>

                {/* Confidence */}
                <div style={{ textAlign: "right", flexShrink: 0, minWidth: 60 }}>
                  <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--foreground-faint)", marginBottom: "0.15rem" }}>
                    Confidence
                  </div>
                  <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 14, fontWeight: 500, color: confColors[p.confidence] }}>
                    {p.confidence.toUpperCase()}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

/* ── Categories Tab ── */

function CategoriesTab({ categories }: { categories: CategoryBreakdown[] }) {
  return (
    <div>
      <h3 style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "1.2rem", fontWeight: 700, color: "var(--foreground)", marginBottom: "1rem" }}>
        Accuracy by Category
      </h3>
      <div
        style={{
          display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 1,
          background: "var(--border)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden",
        }}
      >
        {categories.map((cat) => {
          const accColor = cat.accuracy >= 65 ? "var(--teal)" : cat.accuracy >= 55 ? "var(--ochre)" : "var(--red)";
          return (
            <div key={cat.category} style={{ background: "var(--surface)", padding: "1rem 1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 14, fontWeight: 500, color: "var(--foreground)" }}>{CATEGORY_LABELS[cat.category]}</span>
              <div className="flex gap-4 items-center">
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 14, fontWeight: 500, color: accColor }}>{cat.accuracy.toFixed(1)}%</div>
                  <div style={{ fontSize: 10, color: "var(--foreground-faint)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Accuracy</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 14, fontWeight: 500 }}>{cat.totalCalls}</div>
                  <div style={{ fontSize: 10, color: "var(--foreground-faint)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Calls</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <h3 style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "1.2rem", fontWeight: 700, color: "var(--foreground)", marginTop: "2rem", marginBottom: "1rem" }}>
        Top Predictor by Category
      </h3>
      <div
        style={{
          display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 1,
          background: "var(--border)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden",
        }}
      >
        {categories.map((cat) => (
          <div key={cat.category} style={{ background: "var(--surface)", padding: "1rem 1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span style={{ fontSize: 14, fontWeight: 500, color: "var(--foreground)" }}>{CATEGORY_LABELS[cat.category]}</span>
              <div style={{ fontSize: 12, color: "var(--foreground-muted)", marginTop: "0.15rem" }}>
                Best: {cat.bestPredictor.name} ({cat.bestAccuracy.toFixed(1)}%)
              </div>
            </div>
            <KindTag kind={cat.bestPredictor.kind} />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Main Component ── */

export default function LedgerClient({ data }: { data: LedgerResponse }) {
  const [tab, setTab] = useState<TabKey>("scoreboard");

  const { summary } = data;

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-5xl px-6">
        {/* Header */}
        <div className="pt-10 pb-6">
          <h1 style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "1.8rem", fontWeight: 700, color: "var(--wiki-ink)", marginBottom: "0.15rem" }}>
            The Ledger
          </h1>
          <p style={{ fontSize: 14, color: "var(--wiki-ink-faint)", marginBottom: "1rem" }}>
            Predictions, outcomes, receipts. Every call tracked. Every source ranked.
          </p>
          <p style={{ fontFamily: "var(--font-serif), Georgia, serif", fontStyle: "italic", fontSize: "1.05rem", color: "var(--accent)", paddingLeft: "1rem", borderLeft: "2px solid var(--accent-border)" }}>
            &ldquo;Everyone&rsquo;s got an opinion. This is where we keep score.&rdquo;
          </p>
        </div>

        {/* Summary stats */}
        <div
          style={{
            display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1,
            background: "var(--border)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden",
            marginBottom: "2rem",
          }}
        >
          <StatCard value={String(summary.totalPredictions)} label="Total Predictions" sub={`across ${summary.totalSources} sources`} />
          <StatCard value={`${summary.avgAccuracy.toFixed(1)}%`} label="Avg Accuracy" sub={`+${summary.avgAccuracyDelta.toFixed(1)}% vs last season`} color="var(--teal)" />
          <StatCard value={summary.currentRound} label="Current Round" sub={`Season ${summary.season}`} color="var(--ochre)" />
          <StatCard value={String(summary.pending)} label="Pending Calls" sub="awaiting results" color="var(--accent)" />
        </div>

        {/* Tabs */}
        <div className="flex" style={{ borderBottom: "1px solid rgba(237,228,214,0.14)", marginBottom: "1.5rem" }}>
          {(["scoreboard", "predictions", "categories"] as TabKey[]).map((key) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                padding: "0.6rem 1.25rem", fontSize: 14, fontWeight: 500, cursor: "pointer",
                color: tab === key ? "var(--accent)" : "var(--foreground-muted)",
                borderBottom: `2px solid ${tab === key ? "var(--accent)" : "transparent"}`,
                background: "none", border: "none",
                borderBottomStyle: "solid", borderBottomWidth: 2,
              }}
            >
              {key === "scoreboard" ? "Scoreboard" : key === "predictions" ? "All Predictions" : "By Category"}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="pb-12">
          {tab === "scoreboard" && <ScoreboardTab scoreboard={data.scoreboard} hotZones={data.hotZones} />}
          {tab === "predictions" && <PredictionsTab predictions={data.predictions} />}
          {tab === "categories" && <CategoriesTab categories={data.categories} />}
        </div>
      </div>
    </div>
  );
}

function StatCard({ value, label, sub, color }: { value: string; label: string; sub: string; color?: string }) {
  return (
    <div style={{ background: "var(--surface)", padding: "1.25rem 1rem", textAlign: "center" }}>
      <div style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "2rem", fontWeight: 700, color: color ?? "var(--foreground)", lineHeight: 1.1 }}>
        {value}
      </div>
      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--foreground-muted)", textTransform: "uppercase", letterSpacing: "0.04em", marginTop: "0.25rem" }}>
        {label}
      </div>
      <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 11, color: "var(--foreground-faint)", marginTop: "0.15rem" }}>
        {sub}
      </div>
    </div>
  );
}
