import Link from "next/link";

export const metadata = {
  title: "The Map | Jaromelu",
  description: "How players, teams, rounds and voices connect.",
};

export default function WikiMapPage() {
  return (
    <div className="min-h-screen">
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
          padding: "6rem 2rem",
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--wiki-accent)",
            marginBottom: "0.85rem",
          }}
        >
          The Map
        </div>
        <h1
          style={{
            fontFamily: "var(--font-serif), Georgia, serif",
            fontSize: "clamp(2.2rem, 5vw, 3rem)",
            fontWeight: 700,
            color: "var(--wiki-ink)",
            lineHeight: 1.1,
            marginBottom: "0.6rem",
          }}
        >
          The full graph view is coming.
        </h1>
        <p
          style={{
            fontFamily: "var(--font-serif), Georgia, serif",
            fontStyle: "italic",
            fontSize: "1.05rem",
            color: "var(--wiki-ink-muted)",
            lineHeight: 1.5,
            marginBottom: "2rem",
          }}
        >
          Players, teams, rounds and voices, with every connection between
          them — explorable.
        </p>
        <Link
          href="/wiki"
          style={{
            color: "var(--wiki-accent)",
            fontWeight: 500,
            textDecoration: "none",
            fontSize: "14px",
          }}
        >
          ← Back to the Wiki
        </Link>
      </div>
    </div>
  );
}
