"use client";

import React, { type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { WikiLinkedPages, WikiPageType } from "../wiki-data";
import WikiLink from "./WikiLink";

/* ─── helpers ─── */

function slugToId(text: string): string {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function typeToRoute(pageType: WikiPageType): string {
  return `/wiki/${pageType}`;
}

function extractText(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (React.isValidElement(node)) {
    const props = node.props as Record<string, unknown>;
    if (props.children) return extractText(props.children as ReactNode);
  }
  return "";
}

/* ─── wiki-link pre-processing ─── */

function preprocessWikiLinks(
  content: string,
  linkedPages: WikiLinkedPages
): string {
  return content.replace(/\[\[([^\]]+)\]\]/g, (_match, slug: string) => {
    const linked = linkedPages[slug];
    if (linked) {
      const href = `${typeToRoute(linked.page_type)}/${slug}`;
      return `[${linked.title}](wiki://${href})`;
    }
    return `**${slug}**`;
  });
}

/* ─── custom block pre-processing ───
 *
 * Converts custom markdown conventions into HTML markers
 * that the renderer can detect and style:
 *
 *   :::stats
 *   | Label | Value | Sub |
 *   ...
 *   :::
 *
 *   :::trust
 *   | Rating | Name | Description |
 *   ...
 *   :::
 *
 *   :::timeline
 *   | Year | Color | Title | Description | Signal |
 *   ...
 *   :::
 *
 *   :::final-verdict
 *   text
 *   :::
 */

interface StatCard {
  label: string;
  value: string;
  sub: string;
}

interface TrustItem {
  rating: string;
  name: string;
  nameHtml: string;
  desc: string;
}

interface TimelineStep {
  year: string;
  color: string;
  title: string;
  desc: string;
  signal: string;
}

function parseStatsBlock(block: string): StatCard[] {
  const lines = block.trim().split("\n").filter((l) => l.includes("|"));
  // Skip header and separator
  const dataLines = lines.filter((l) => !l.match(/^\|[\s-|]+$/)).slice(1);
  return dataLines.map((line) => {
    const cells = line.split("|").map((c) => c.trim()).filter(Boolean);
    return { label: cells[0] || "", value: cells[1] || "", sub: cells[2] || "" };
  });
}

function parseTrustBlock(block: string): TrustItem[] {
  const lines = block.trim().split("\n").filter((l) => l.includes("|"));
  const dataLines = lines.filter((l) => !l.match(/^\|[\s-|]+$/)).slice(1);
  return dataLines.map((line) => {
    const cells = line.split("|").map((c) => c.trim()).filter(Boolean);
    return {
      rating: cells[0] || "",
      name: cells[1] || "",
      nameHtml: cells[1] || "",
      desc: cells[2] || "",
    };
  });
}

function parseTimelineBlock(block: string): TimelineStep[] {
  const lines = block.trim().split("\n").filter((l) => l.includes("|"));
  const dataLines = lines.filter((l) => !l.match(/^\|[\s-|]+$/)).slice(1);
  return dataLines.map((line) => {
    const cells = line.split("|").map((c) => c.trim()).filter(Boolean);
    return {
      year: cells[0] || "",
      color: cells[1] || "gray",
      title: cells[2] || "",
      desc: cells[3] || "",
      signal: cells[4] || "",
    };
  });
}

const RATING_COLORS: Record<string, string> = {
  BULLISH: "green", BUY: "green", SOLID: "green", HIT: "green",
  HOLD: "amber", NEUTRAL: "amber", PLAUSIBLE: "amber",
  BEARISH: "red", SELL: "red", AVOID: "red", MISS: "red", SPECULATIVE: "red",
  CAPTAIN: "purple",
};

/* ─── blockquote variant detection ─── */

type BoxVariant = "callout" | "mechanism" | "verdict" | "warning";

const BOX_PREFIXES: Record<string, BoxVariant> = {
  "Callout:": "callout",
  "Mechanism:": "mechanism",
  "Verdict:": "verdict",
  "Warning:": "warning",
};

const BOX_CLASSES: Record<BoxVariant, string> = {
  callout: "wiki-callout",
  mechanism: "wiki-mechanism",
  verdict: "wiki-verdict",
  warning: "wiki-warning",
};

function detectBoxVariant(children: ReactNode): BoxVariant | null {
  const text = extractText(children);
  for (const [prefix, variant] of Object.entries(BOX_PREFIXES)) {
    if (text.startsWith(prefix)) return variant;
  }
  return null;
}

/* ─── inline tag detection ─── */

type TagColor = "teal" | "amber" | "purple" | "green" | "red" | "accent" | "gray";

const TAG_COLORS: Record<string, TagColor> = {
  BUY: "green", SELL: "red", HOLD: "amber", CAPTAIN: "purple",
  AVOID: "red", BREAKOUT: "teal", SOLID: "green", PLAUSIBLE: "amber",
  SPECULATIVE: "red", BULLISH: "green", BEARISH: "red", NEUTRAL: "gray",
};

function renderTag(text: string): ReactNode {
  const match = text.match(/^\[([A-Z_]+)\]$/);
  if (!match) return null;
  const key = match[1];
  const colorKey = TAG_COLORS[key];
  if (!colorKey) return null;
  return <span className={`wiki-tag ${colorKey}`}>{key}</span>;
}

/* ─── custom block rendering ─── */

function renderCustomBlocks(content: string): string {
  // Replace :::stats ... ::: with a placeholder that won't be parsed as markdown
  // We'll handle these blocks separately
  return content;
}

/* ─── main component ─── */

interface MarkdownRendererProps {
  content: string;
  linkedPages: WikiLinkedPages;
}

export default function MarkdownRenderer({
  content,
  linkedPages,
}: MarkdownRendererProps) {
  // Split content into segments: regular markdown and custom blocks
  const segments: Array<{ type: "md" | "stats" | "trust" | "timeline" | "final-verdict"; content: string }> = [];
  const blockRegex = /^:::(stats|trust|timeline|final-verdict)\s*\n([\s\S]*?)^:::\s*$/gm;
  let lastIndex = 0;

  const processed = preprocessWikiLinks(content, linkedPages);
  let match;

  while ((match = blockRegex.exec(processed)) !== null) {
    // Push any markdown before this block
    if (match.index > lastIndex) {
      segments.push({ type: "md", content: processed.slice(lastIndex, match.index) });
    }
    segments.push({ type: match[1] as "stats" | "trust" | "timeline" | "final-verdict", content: match[2] });
    lastIndex = match.index + match[0].length;
  }
  // Push remaining markdown
  if (lastIndex < processed.length) {
    segments.push({ type: "md", content: processed.slice(lastIndex) });
  }

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === "stats") {
          const cards = parseStatsBlock(seg.content);
          return (
            <div key={i} className="wiki-stat-cards">
              {cards.map((card, ci) => (
                <div key={ci} className="wiki-stat-card">
                  <div className="label">{card.label}</div>
                  <div className="value">{card.value}</div>
                  <div className="sub">{card.sub}</div>
                </div>
              ))}
            </div>
          );
        }

        if (seg.type === "trust") {
          const items = parseTrustBlock(seg.content);
          return (
            <div key={i} className="wiki-trust-list">
              {items.map((item, ti) => {
                const ratingColor = RATING_COLORS[item.rating.toUpperCase()] || "gray";
                return (
                  <div key={ti} className="wiki-trust-item">
                    <div className="wiki-trust-rating">
                      <span className={`wiki-tag ${ratingColor}`}>{item.rating}</span>
                    </div>
                    <div className="wiki-trust-body">
                      <strong dangerouslySetInnerHTML={{ __html: item.name }} />
                      <p dangerouslySetInnerHTML={{ __html: item.desc }} />
                    </div>
                  </div>
                );
              })}
            </div>
          );
        }

        if (seg.type === "timeline") {
          const steps = parseTimelineBlock(seg.content);
          return (
            <div key={i} className="wiki-timeline">
              {steps.map((step, si) => (
                <div key={si} className="wiki-timeline-step">
                  <div className={`wiki-timeline-dot ${step.color}`}>{step.year}</div>
                  <div className="wiki-timeline-body">
                    <h4>{step.title}</h4>
                    <p dangerouslySetInnerHTML={{ __html: step.desc }} />
                    {step.signal && <p className="signal" dangerouslySetInnerHTML={{ __html: step.signal }} />}
                  </div>
                </div>
              ))}
            </div>
          );
        }

        if (seg.type === "final-verdict") {
          return (
            <div key={i} className="wiki-final-verdict">
              <p className="kicker">Jaromelu&apos;s Call</p>
              <MarkdownSegment content={seg.content.trim()} />
            </div>
          );
        }

        // Regular markdown
        return <MarkdownSegment key={i} content={seg.content} />;
      })}
    </>
  );
}

/* ─── markdown segment renderer ─── */

function MarkdownSegment({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h2: ({ children }) => {
          const id = slugToId(String(children));
          return (
            <section id={id}>
              <h2>{children}</h2>
            </section>
          );
        },

        h3: ({ children }) => {
          const id = slugToId(String(children));
          return <h3 id={id}>{children}</h3>;
        },

        h4: ({ children }) => (
          <h4
            style={{
              fontSize: "11px", fontWeight: 600, letterSpacing: "0.12em",
              textTransform: "uppercase" as const,
              color: "var(--wiki-ink-faint)",
              marginTop: "1.5rem", marginBottom: "0.5rem",
            }}
          >
            {children}
          </h4>
        ),

        p: ({ children }) => <p>{children}</p>,

        blockquote: ({ children }) => {
          const variant = detectBoxVariant(children);
          if (variant) return <div className={BOX_CLASSES[variant]}>{children}</div>;
          return <blockquote>{children}</blockquote>;
        },

        a: ({ href, children }) => {
          if (href?.startsWith("wiki://")) {
            return <WikiLink href={href.replace("wiki://", "")}>{children}</WikiLink>;
          }
          return (
            <a href={href} style={{ color: "var(--wiki-accent, #b85c38)" }} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          );
        },

        code: ({ children, className }) => {
          const text = String(children);
          if (!className) {
            const tag = renderTag(text);
            if (tag) return tag;
          }
          return (
            <code style={{
              fontSize: "14px", padding: "0.1rem 0.4rem", borderRadius: "2px",
              background: "var(--wiki-gray-bg)", color: "var(--wiki-ink-muted)",
            }}>
              {children}
            </code>
          );
        },

        strong: ({ children }) => <strong>{children}</strong>,
        em: ({ children }) => <em style={{ color: "var(--wiki-ink-faint)" }}>{children}</em>,
        ul: ({ children }) => <ul>{children}</ul>,
        ol: ({ children }) => <ol>{children}</ol>,
        table: ({ children }) => <div style={{ overflowX: "auto" }}><table>{children}</table></div>,
        thead: ({ children }) => <thead>{children}</thead>,
        th: ({ children }) => <th>{children}</th>,
        td: ({ children }) => <td>{children}</td>,
        hr: () => <hr />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
