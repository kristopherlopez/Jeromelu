"use client";

import Link from "next/link";
import { Clock, ChevronLeft } from "lucide-react";
import type {
  WikiPageDetail,
  WikiRevisionItem,
  WikiLinkedPages,
  WikiPageType,
} from "../wiki-data";
import MarkdownRenderer from "./MarkdownRenderer";
import "../wiki.css";

/* ─── helpers ─── */

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function typeLabel(type: WikiPageType): string {
  return (
    {
      player: "Player",
      team: "Team",
      advisor: "Advisor",
      round: "Round",
      channel: "Channel",
    }[type] || type
  );
}

function extractSections(content: string): { id: string; title: string }[] {
  return Array.from(content.matchAll(/^## (.+)$/gm)).map((m) => ({
    title: m[1],
    id: m[1].toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
  }));
}

/* ─── component ─── */

interface WikiPageClientProps {
  page: WikiPageDetail;
  revisions: WikiRevisionItem[];
  linkedPages: WikiLinkedPages;
}

export default function WikiPageClient({
  page,
  revisions,
  linkedPages,
}: WikiPageClientProps) {
  const sections = extractSections(page.content);

  return (
    <div data-box-style="top-rule">
      {/* ── Sticky nav: breadcrumb + section anchors ── */}
      <nav className="wiki-nav">
        <div className="wiki-nav-back">
          <Link href="/wiki" className="wiki-nav-link">
            <ChevronLeft size={14} className="wiki-nav-icon" />
            Wiki
          </Link>
          <span className="wiki-nav-sep">›</span>
          <Link href={`/wiki?type=${page.page_type}`} className="wiki-nav-link">
            {typeLabel(page.page_type)}s
          </Link>
        </div>
        {sections.length > 1 && (
          <div className="wiki-nav-sections">
            {sections.map((sec) => (
              <a key={sec.id} href={`#${sec.id}`}>
                {sec.title}
              </a>
            ))}
          </div>
        )}
      </nav>

      {/* ── Hero header ── */}
      <header className="wiki-hero">
        <p className="kicker">{typeLabel(page.page_type)}</p>
        {page.channel?.logo_url && (
          // Channel avatar (YouTube thumbnail / podcast cover art / etc.).
          // Plain <img> rather than next/image since the YouTube CDN
          // (yt3.ggpht.com) isn't pre-allowlisted.
          <img
            src={page.channel.logo_url}
            alt=""
            width={96}
            height={96}
            style={{
              width: 96,
              height: 96,
              borderRadius: 12,
              objectFit: "cover",
              marginBottom: "0.75rem",
              display: "block",
            }}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        )}
        <h1>{page.title}</h1>
        {page.summary && <p className="subtitle">{page.summary}</p>}
        <div className="wiki-hero-meta">
          <span>Updated {formatRelative(page.updated_at)}</span>
          <span>
            {page.revision_count} revision{page.revision_count !== 1 ? "s" : ""}
          </span>
          {page.status !== "published" && (
            <span>
              <span
                className="wiki-tag amber"
                style={{ fontSize: "10px", marginLeft: "0.3rem" }}
              >
                {page.status}
              </span>
            </span>
          )}
        </div>
        <div className="wiki-hero-divider" />
      </header>

      {/* ── Main content ── */}
      <div className="wiki-content">
        {page.content ? (
          <MarkdownRenderer content={page.content} linkedPages={linkedPages} />
        ) : (
          <div
            style={{
              textAlign: "center",
              padding: "5rem 0",
              color: "var(--wiki-ink-faint, #71717a)",
            }}
          >
            <p style={{ fontSize: "15px" }}>
              This page is a stub. Content will be generated as sources are processed.
            </p>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <footer
        style={{
          textAlign: "center",
          padding: "3rem 2rem",
          borderTop: "1px solid var(--wiki-border, rgba(255,255,255,0.08))",
          fontSize: "12px",
          color: "var(--wiki-ink-faint, #71717a)",
          letterSpacing: "0.05em",
        }}
      >
        <p>
          Wiki page maintained by{" "}
          <strong style={{ color: "var(--wiki-ink-muted, #a1a1aa)", fontWeight: 500 }}>
            Jaromelu
          </strong>{" "}
          — AI NRL SuperCoach Analyst
        </p>
        {revisions.length > 0 && (
          <p style={{ marginTop: "0.4rem" }}>
            Last updated: {formatRelative(page.updated_at)}
            {revisions[0].section_heading && (
              <> — {revisions[0].summary}</>
            )}
          </p>
        )}
      </footer>
    </div>
  );
}
