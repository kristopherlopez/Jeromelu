"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { InsightDetail, ArticleType } from "../insights-data";
import { ARTICLE_TYPE_LABELS } from "../insights-data";

const TYPE_COLORS: Record<ArticleType, { color: string; bg: string; border: string }> = {
  tips: { color: "var(--accent)", bg: "var(--accent-bg)", border: "var(--accent-border)" },
  totw: { color: "var(--teal)", bg: "var(--teal-bg)", border: "var(--teal-border)" },
  trades: { color: "var(--slate)", bg: "var(--slate-bg)", border: "var(--slate-border)" },
  captains: { color: "var(--lilac)", bg: "var(--lilac-bg)", border: "rgba(168,152,200,0.22)" },
  stocks: { color: "var(--ochre)", bg: "var(--ochre-bg)", border: "var(--ochre-border)" },
  consensus: { color: "var(--terracotta)", bg: "var(--terracotta-bg)", border: "rgba(184,92,56,0.22)" },
};

function TypeBadge({ type }: { type: ArticleType }) {
  const c = TYPE_COLORS[type];
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        padding: "0.15rem 0.5rem",
        borderRadius: "3px",
        background: c.bg,
        color: c.color,
        border: `1px solid ${c.border}`,
      }}
    >
      {ARTICLE_TYPE_LABELS[type]}
    </span>
  );
}

interface ArticleClientProps {
  article: InsightDetail | null;
}

export default function ArticleClient({ article }: ArticleClientProps) {
  if (!article) {
    return (
      <div className="min-h-screen">
        <div
          className="mx-auto max-w-5xl px-6"
          style={{
            paddingTop: "4rem",
            textAlign: "center",
          }}
        >
          <p
            style={{
              fontSize: "15px",
              fontWeight: 500,
              color: "var(--foreground-secondary)",
              marginBottom: "0.75rem",
            }}
          >
            Article not found
          </p>
          <Link
            href="/insights"
            style={{
              fontSize: "13px",
              color: "var(--accent)",
              textDecoration: "none",
            }}
          >
            &larr; Back to The Analysis
          </Link>
        </div>
      </div>
    );
  }

  const date = new Date(article.created_at);

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-5xl px-6">
        {/* Back link */}
        <div className="pt-6">
          <Link
            href="/insights"
            style={{
              fontSize: "13px",
              color: "var(--foreground-faint)",
              textDecoration: "none",
            }}
          >
            &larr; The Analysis
          </Link>
        </div>

        {/* Article header */}
        <div className="pt-6 pb-6">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.6rem",
              marginBottom: "0.75rem",
            }}
          >
            <TypeBadge type={article.article_type} />
            <span
              style={{
                fontFamily: "var(--font-geist-mono)",
                fontSize: "11px",
                color: "var(--foreground-faint)",
              }}
            >
              Round {article.effective_round} &middot; Season {article.season}
            </span>
          </div>

          <h1
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              fontSize: "2.2rem",
              fontWeight: 700,
              color: "var(--foreground)",
              marginBottom: "0.5rem",
              lineHeight: 1.15,
            }}
          >
            {article.title}
          </h1>

          <p
            style={{
              fontFamily: "var(--font-geist-mono)",
              fontSize: "12px",
              color: "var(--foreground-faint)",
            }}
          >
            Published{" "}
            {date.toLocaleDateString("en-AU", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </p>
        </div>

        {/* Article content */}
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "2rem 2rem",
            marginBottom: "1.5rem",
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h2: ({ children }) => (
                <h2
                  style={{
                    fontFamily: "var(--font-serif), Georgia, serif",
                    fontSize: "1.35rem",
                    fontWeight: 600,
                    color: "var(--foreground)",
                    marginTop: "2rem",
                    marginBottom: "0.75rem",
                    paddingBottom: "0.5rem",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3
                  style={{
                    fontFamily: "var(--font-serif), Georgia, serif",
                    fontSize: "1.15rem",
                    fontWeight: 600,
                    color: "var(--foreground)",
                    marginTop: "1.5rem",
                    marginBottom: "0.5rem",
                  }}
                >
                  {children}
                </h3>
              ),
              p: ({ children }) => (
                <p
                  style={{
                    fontSize: "14px",
                    lineHeight: 1.7,
                    color: "var(--foreground-secondary)",
                    margin: "0 0 1rem 0",
                  }}
                >
                  {children}
                </p>
              ),
              strong: ({ children }) => (
                <strong
                  style={{ fontWeight: 600, color: "var(--foreground)" }}
                >
                  {children}
                </strong>
              ),
              em: ({ children }) => (
                <em style={{ color: "var(--foreground-muted)" }}>
                  {children}
                </em>
              ),
              ul: ({ children }) => (
                <ul
                  style={{
                    paddingLeft: "1.25rem",
                    margin: "0 0 1rem 0",
                  }}
                >
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol
                  style={{
                    paddingLeft: "1.25rem",
                    margin: "0 0 1rem 0",
                  }}
                >
                  {children}
                </ol>
              ),
              li: ({ children }) => (
                <li
                  style={{
                    fontSize: "14px",
                    lineHeight: 1.6,
                    color: "var(--foreground-secondary)",
                    marginBottom: "0.25rem",
                  }}
                >
                  {children}
                </li>
              ),
              blockquote: ({ children }) => (
                <blockquote
                  style={{
                    borderLeft: "2px solid var(--accent-border)",
                    paddingLeft: "1rem",
                    margin: "1rem 0",
                    color: "var(--foreground-muted)",
                    fontStyle: "italic",
                  }}
                >
                  {children}
                </blockquote>
              ),
              table: ({ children }) => (
                <div
                  style={{
                    overflowX: "auto",
                    margin: "1rem 0",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                  }}
                >
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead style={{ background: "var(--background-deep)" }}>
                  {children}
                </thead>
              ),
              th: ({ children }) => (
                <th
                  style={{
                    padding: "0.6rem 1rem",
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--foreground-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    textAlign: "left",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td
                  style={{
                    padding: "0.6rem 1rem",
                    fontSize: "13px",
                    color: "var(--foreground-secondary)",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {children}
                </td>
              ),
              hr: () => (
                <hr
                  style={{
                    border: "none",
                    borderTop: "1px solid var(--border)",
                    margin: "2rem 0",
                  }}
                />
              ),
              code: ({ children, className }) => {
                if (className) {
                  return (
                    <code
                      style={{
                        fontSize: "13px",
                        padding: "0.1rem 0.4rem",
                        borderRadius: "3px",
                        background: "var(--background-deep)",
                        color: "var(--foreground-muted)",
                      }}
                    >
                      {children}
                    </code>
                  );
                }
                return (
                  <code
                    style={{
                      fontSize: "13px",
                      fontFamily: "var(--font-geist-mono)",
                      padding: "0.1rem 0.4rem",
                      borderRadius: "3px",
                      background: "var(--background-deep)",
                      color: "var(--accent)",
                    }}
                  >
                    {children}
                  </code>
                );
              },
            }}
          >
            {article.content}
          </ReactMarkdown>
        </div>

        {/* Source attribution */}
        {article.sources.length > 0 && (
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "1rem 1.25rem",
              marginBottom: "2rem",
            }}
          >
            <div
              style={{
                fontSize: "11px",
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "var(--foreground-faint)",
                marginBottom: "0.5rem",
              }}
            >
              Sources
            </div>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "0.5rem",
              }}
            >
              {article.sources.map((s) => (
                <span
                  key={s.source_id}
                  style={{
                    fontSize: "13px",
                    color: "var(--foreground-secondary)",
                    padding: "0.25rem 0.6rem",
                    borderRadius: "4px",
                    background: "var(--background-deep)",
                    border: "1px solid var(--border)",
                  }}
                >
                  {s.title}
                  {s.creator_name && (
                    <span
                      style={{
                        color: "var(--foreground-faint)",
                        marginLeft: "0.3rem",
                      }}
                    >
                      by {s.creator_name}
                    </span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="pb-12" />
      </div>
    </div>
  );
}
