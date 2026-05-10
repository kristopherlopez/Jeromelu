import Link from "next/link";
import { notFound } from "next/navigation";

import { API_BASE, apiFetch } from "@/lib/api";
import type { FaceGroup, FaceGroupsResponse, SourceDetailResponse } from "@/lib/types";

import { ArrowLeft } from "lucide-react";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ sourceId: string }>;
}

function fmtTs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function groupTitle(g: FaceGroup): string {
  if (g.person_id === null) return "Unassigned";
  return g.person_name ?? `Person ${g.person_id.slice(0, 8)}`;
}

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export default async function SourceFacesPage({ params }: Props) {
  const { sourceId } = await params;

  // Two reads in parallel — the source detail (for the title) and the
  // face-groups payload. If either 404s we bail to the standard page.
  let source: SourceDetailResponse["source"];
  let groups: FaceGroupsResponse;
  try {
    const [detail, gs] = await Promise.all([
      apiFetch<SourceDetailResponse>(`/api/sources/${sourceId}`),
      apiFetch<FaceGroupsResponse>(`/api/sources/${sourceId}/face-groups`),
    ]);
    source = detail.source;
    groups = gs;
  } catch {
    notFound();
  }

  // Pre-sort: matched groups by size descending, then the unassigned
  // bucket last. Unassigned tends to dominate by count and would push
  // matched persons off-screen if it sorted by detection_count alone.
  const matched = groups.groups.filter((g) => g.person_id !== null);
  const unassigned = groups.groups.find((g) => g.person_id === null);
  const ordered: FaceGroup[] = [...matched, ...(unassigned ? [unassigned] : [])];

  const totalAttributed = matched.reduce((acc, g) => acc + g.detection_count, 0);
  const totalUnassigned = unassigned?.detection_count ?? 0;

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <Link
        href={`/wiki/source/${sourceId}`}
        className="mb-4 inline-flex items-center gap-1.5 text-xs"
        style={{ color: "var(--foreground-secondary)" }}
      >
        <ArrowLeft size={14} />
        Back to source
      </Link>

      <h1 className="text-lg font-semibold">{source.title}</h1>
      <p className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        Faces detected per visual ID. {groups.total_faces.toLocaleString()} detections —
        {" "}{totalAttributed.toLocaleString()} attributed
        ({groups.total_faces > 0 ? pct(totalAttributed / groups.total_faces) : "—"}),
        {" "}{totalUnassigned.toLocaleString()} unassigned.
      </p>

      <div className="mt-6 flex flex-col gap-6">
        {ordered.map((g) => (
          <FaceGroupSection
            key={g.person_id ?? "unassigned"}
            sourceId={sourceId}
            group={g}
          />
        ))}
      </div>
    </main>
  );
}

function FaceGroupSection({
  sourceId,
  group,
}: {
  sourceId: string;
  group: FaceGroup;
}) {
  const isUnassigned = group.person_id === null;
  return (
    <section
      className="rounded border p-4"
      style={{
        borderColor: isUnassigned ? "var(--border)" : "var(--accent)",
        backgroundColor: "var(--surface)",
      }}
    >
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold">
          {groupTitle(group)}
          <span
            className="ml-2 text-xs font-normal"
            style={{ color: "var(--foreground-ghost)" }}
          >
            {group.detection_count.toLocaleString()} detections
            {group.avg_similarity !== null
              ? ` · avg similarity ${pct(group.avg_similarity)}`
              : ""}
            {" "}· avg det {pct(group.avg_det_score)}
          </span>
        </h2>
      </header>

      {group.samples.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
          No samples (face-track has detections but they fell outside the
          sampling bins).
        </p>
      ) : (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6">
          {group.samples.map((s) => (
            <FaceThumb key={`${s.ts}-${s.bbox.join(",")}`} sourceId={sourceId} sample={s} />
          ))}
        </ul>
      )}
    </section>
  );
}

function FaceThumb({
  sourceId,
  sample,
}: {
  sourceId: string;
  sample: { ts: number; bbox: [number, number, number, number]; det_score: number };
}) {
  const bboxParam = sample.bbox.map((n) => n.toFixed(3)).join(",");
  // Goes back to the source page seeked to this ts so the operator can
  // inspect the moment in context.
  const seekHref = `/wiki/source/${sourceId}?t=${sample.ts.toFixed(1)}`;
  const cropUrl = `${API_BASE}/api/sources/${sourceId}/face-crop?ts=${sample.ts}&bbox=${encodeURIComponent(bboxParam)}`;
  return (
    <li>
      <Link href={seekHref} className="block">
        <div
          className="overflow-hidden rounded border"
          style={{ borderColor: "var(--border)", aspectRatio: "1 / 1" }}
        >
          {/* The crop endpoint serves long-cacheable JPEGs so the browser
              keeps thumbnails warm across navigations. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={cropUrl}
            alt={`face at ${fmtTs(sample.ts)}`}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        </div>
        <div
          className="mt-1 text-[10px] tabular-nums"
          style={{ color: "var(--foreground-ghost)" }}
        >
          {fmtTs(sample.ts)} · det {pct(sample.det_score)}
        </div>
      </Link>
    </li>
  );
}
