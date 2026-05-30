"""Deterministic YouTube-native source discovery.

This module handles the bulk YouTube discovery case without involving the
Claude source-discovery loop. It reads the known YouTube surface from the DB,
passes those IDs into the existing YouTube Data API helpers so results are
filtered before scoring, enriches novel IDs with batched metadata, then writes
only reviewable candidates to ``miner_candidates``.

The agentic loop remains available for off-platform and long-tail work where
structured YouTube search is not enough.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from jeromelu_shared.db import Channel, MinerCandidate, Source
from jeromelu_shared.youtube import extract_video_id
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..youtube import client as youtube_api

DEFAULT_CHANNEL_QUERIES: tuple[str, ...] = (
    "NRL analysis podcast",
    "NRL injury news",
    "NRL team list Tuesday",
    "NRLW analysis",
    "State of Origin rugby league podcast",
    "rugby league tactics NRL",
)

DEFAULT_VIDEO_QUERIES: tuple[str, ...] = (
    "NRL analysis latest",
    "NRL injury update",
    "NRL team lists",
    "NRLW highlights analysis",
)

DEFAULT_HARVEST_QUERIES: tuple[str, ...] = (
    "NRL round highlights analysis",
    "NRL press conference",
    "State of Origin highlights analysis",
)

DEFAULT_MIN_SCORE = 0.55

_RELEVANCE_TERMS: tuple[str, ...] = (
    "nrl",
    "nrlw",
    "rugby league",
    "national rugby league",
    "state of origin",
    "origin",
    "super league",
    "nsw blues",
    "queensland maroons",
    "kangaroos",
    "kiwis",
)

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "injury": ("injury", "injuries", "casualty", "casualty ward", "late mail"),
    "supercoach": ("supercoach", "fantasy", "dream team"),
    "nrlw": ("nrlw", "women's rugby league", "womens rugby league"),
    "origin": ("state of origin", "origin", "blues", "maroons"),
    "international": ("kangaroos", "kiwis", "world cup", "pacific championship", "international"),
    "junior": ("junior", "under 19", "under-19", "sg ball", "harold matthews", "jersey flegg"),
    "classic": ("classic", "retro", "archive", "old game"),
    "rules-officiating": ("referee", "bunker", "sin bin", "judiciary", "match review", "officiating"),
    "match": ("highlights", "full match", "press conference", "post-match", "post match", "preview", "review"),
    "tactical": ("tactics", "tactical", "breakdown", "analysis", "shape", "defence", "attack"),
    "news": ("news", "update", "team list", "team lists", "signing", "contract", "rumour", "rumor"),
    "opinion": ("podcast", "opinion", "debate", "reaction", "show"),
    "player-content": ("interview", "player", "players", "captain", "coach"),
}


@dataclass(frozen=True)
class KnownYouTubeIds:
    """Known platform IDs used for deterministic server-side dedupe."""

    channel_ids: set[str]
    video_ids: set[str]


@dataclass
class CandidateDraft:
    """Insert-ready candidate for ``miner_candidates``."""

    kind: str
    external_id: str
    url: str
    title: str
    description: str | None
    channel_external_id: str | None
    content_categories: list[str]
    score: float
    score_reasons: list[str]
    metadata: dict[str, Any]
    discovered_via: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "external_id": self.external_id,
            "url": self.url,
            "title": self.title,
            "channel_external_id": self.channel_external_id,
            "content_categories": self.content_categories,
            "score": self.score,
            "score_reasons": self.score_reasons,
            "discovered_via": self.discovered_via,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PersistSummary:
    inserted: int
    duplicates: int
    candidate_ids: list[str]


@dataclass
class DeterministicYouTubeDiscoveryResult:
    run_id: str
    dry_run: bool
    channel_queries: list[str]
    video_queries: list[str]
    harvest_queries: list[str]
    related_channel_ids: list[str]
    known_channels_at_start: int
    known_videos_at_start: int
    channel_seeds_seen: int
    video_seeds_seen: int
    candidates_scored: int
    candidates_below_threshold: int
    candidates_missing_api_metadata: int
    candidates_inserted: int
    duplicates_skipped: int
    candidate_ids: list[str]
    candidates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def candidates_selected(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates_selected"] = self.candidates_selected
        return payload


@dataclass
class _ChannelSeed:
    channel_id: str
    title: str = ""
    description: str = ""
    signals: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class _VideoSeed:
    video_id: str
    channel_id: str = ""
    channel_title: str = ""
    title: str = ""
    description: str = ""
    published_at: str = ""
    url: str = ""
    signals: list[dict[str, Any]] = field(default_factory=list)


def _clean_queries(queries: Sequence[str] | None, defaults: tuple[str, ...]) -> list[str]:
    source = defaults if queries is None else queries
    return [q.strip() for q in source if q and q.strip()]


def load_known_youtube_ids(session: Session) -> KnownYouTubeIds:
    """Load YouTube channel and video IDs already tracked or queued.

    Channels dedupe against ``channels`` and channel candidates. Videos dedupe
    against canonical YouTube ``sources`` plus video candidates. This is more
    complete than exact URL matching because it normalises youtu.be/watch URLs
    to the same video ID before filtering.
    """

    tracked_channels = {
        row[0]
        for row in session.execute(
            select(Channel.external_id).where(
                Channel.platform == "youtube",
                Channel.external_id.isnot(None),
            )
        ).all()
        if row[0]
    }
    candidate_channels = {
        row[0]
        for row in session.execute(
            select(MinerCandidate.external_id).where(
                MinerCandidate.platform == "youtube",
                MinerCandidate.kind == "channel",
            )
        ).all()
        if row[0]
    }
    source_videos = {
        video_id
        for row in session.execute(
            select(Source.canonical_url).where(
                Source.source_type == "youtube",
                Source.canonical_url.isnot(None),
            )
        ).all()
        for video_id in [extract_video_id(row[0])]
        if video_id
    }
    candidate_videos = {
        row[0]
        for row in session.execute(
            select(MinerCandidate.external_id).where(
                MinerCandidate.platform == "youtube",
                MinerCandidate.kind == "video",
            )
        ).all()
        if row[0]
    }
    return KnownYouTubeIds(
        channel_ids=tracked_channels | candidate_channels,
        video_ids=source_videos | candidate_videos,
    )


def _signal(mode: str, query: str | None = None, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"mode": mode}
    if query:
        out["query"] = query
    out.update({k: v for k, v in extra.items() if v not in (None, "")})
    return out


def _add_channel_seed(
    seeds: dict[str, _ChannelSeed],
    *,
    channel_id: str | None,
    known_channel_ids: set[str],
    title: str = "",
    description: str = "",
    signal: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> bool:
    if not channel_id or channel_id in known_channel_ids:
        return False
    seed = seeds.get(channel_id)
    if seed is None:
        seed = _ChannelSeed(channel_id=channel_id)
        seeds[channel_id] = seed
    if title and not seed.title:
        seed.title = title
    if description and not seed.description:
        seed.description = description
    seed.signals.append(signal)
    if context:
        seed.context.update({k: v for k, v in context.items() if v not in (None, "")})
    return True


def _add_video_seed(
    seeds: dict[str, _VideoSeed],
    *,
    video_id: str | None,
    known_video_ids: set[str],
    channel_id: str = "",
    channel_title: str = "",
    title: str = "",
    description: str = "",
    published_at: str = "",
    url: str = "",
    signal: dict[str, Any],
) -> bool:
    if not video_id or video_id in known_video_ids:
        return False
    seed = seeds.get(video_id)
    if seed is None:
        seed = _VideoSeed(video_id=video_id)
        seeds[video_id] = seed
    if channel_id and not seed.channel_id:
        seed.channel_id = channel_id
    if channel_title and not seed.channel_title:
        seed.channel_title = channel_title
    if title and not seed.title:
        seed.title = title
    if description and not seed.description:
        seed.description = description
    if published_at and not seed.published_at:
        seed.published_at = published_at
    if url and not seed.url:
        seed.url = url
    seed.signals.append(signal)
    return True


def _as_text(*parts: Any) -> str:
    return " ".join(str(part or "") for part in parts).lower()


def _matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    return [term for term in terms if term in text]


def _categories_for_text(text: str, *, fallback: str) -> list[str]:
    categories = [category for category, keywords in _CATEGORY_KEYWORDS.items() if _matched_terms(text, keywords)]
    if not categories:
        categories = [fallback]
    return categories[:4]


def _first_signal_summary(signals: list[dict[str, Any]]) -> str:
    if not signals:
        return "deterministic_youtube"
    modes = []
    queries = []
    for item in signals:
        mode = item.get("mode")
        query = item.get("query")
        if mode and mode not in modes:
            modes.append(str(mode))
        if query and query not in queries:
            queries.append(str(query))
    mode_text = "+".join(modes) if modes else "youtube_api"
    if queries:
        return f"deterministic_youtube:{mode_text}:{queries[0]}"
    return f"deterministic_youtube:{mode_text}"


def _bounded_score(score: float) -> float:
    return round(max(0.0, min(score, 1.0)), 2)


def _ensure_two_reasons(reasons: list[str]) -> list[str]:
    if len(reasons) == 1:
        reasons.append("Captured by the deterministic YouTube Data API sweep for human review.")
    if not reasons:
        reasons = [
            "Captured by the deterministic YouTube Data API sweep.",
            "Queued for human review before promotion into canonical tables.",
        ]
    return reasons[:5]


def _numeric_reason(label: str, value: Any) -> str | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return f"YouTube reports {n:,} {label}."


def _score_channel(seed: _ChannelSeed, stats: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    text = _as_text(
        seed.title,
        seed.description,
        stats.get("title"),
        stats.get("description"),
        " ".join(str(s.get("query", "")) for s in seed.signals),
        seed.context.get("first_seen_video_title"),
    )
    result_text = _as_text(seed.title, seed.description, stats.get("title"), stats.get("description"))
    categories = _categories_for_text(text, fallback="analysis")
    result_relevance = _matched_terms(result_text, _RELEVANCE_TERMS)

    score = 0.35
    reasons: list[str] = []
    if result_relevance:
        score += 0.2
        reasons.append(f"Channel metadata includes NRL signal: {', '.join(result_relevance[:3])}.")
    else:
        reasons.append("Surfaced by NRL-focused query, but channel snippet has weak explicit NRL wording.")

    if seed.context.get("first_seen_video_title"):
        score += 0.06
        reasons.append(f"First seen via video: {seed.context['first_seen_video_title'][:90]}.")

    video_count = stats.get("video_count")
    if isinstance(video_count, int) and video_count >= 25:
        score += 0.08
        reasons.append(f"YouTube reports {video_count:,} uploaded videos.")
    elif isinstance(video_count, int) and video_count > 0:
        score += 0.04
        reasons.append(f"YouTube reports {video_count:,} uploaded videos.")

    subs = stats.get("subs")
    if isinstance(subs, int) and subs >= 10_000:
        score += 0.08
        reasons.append(f"YouTube reports {subs:,} subscribers.")
    elif isinstance(subs, int) and subs >= 1_000:
        score += 0.05
        reasons.append(f"YouTube reports {subs:,} subscribers.")

    if stats.get("country") == "AU":
        score += 0.04
        reasons.append("YouTube marks the channel country as AU.")

    if len(seed.signals) > 1:
        score += 0.04
        reasons.append(f"Found through {len(seed.signals)} deterministic signals.")

    if not result_relevance:
        score = min(score, 0.49)

    return _bounded_score(score), _ensure_two_reasons(reasons), categories


def _score_video(seed: _VideoSeed, stats: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    text = _as_text(
        seed.title,
        seed.description,
        seed.channel_title,
        stats.get("title"),
        stats.get("description"),
        stats.get("channel_title"),
        " ".join(stats.get("tags") or []),
        " ".join(str(s.get("query", "")) for s in seed.signals),
    )
    result_text = _as_text(
        seed.title,
        seed.description,
        seed.channel_title,
        stats.get("title"),
        stats.get("description"),
        stats.get("channel_title"),
        " ".join(stats.get("tags") or []),
    )
    categories = _categories_for_text(text, fallback="news")
    result_relevance = _matched_terms(result_text, _RELEVANCE_TERMS)

    score = 0.32
    reasons: list[str] = []
    if result_relevance:
        score += 0.22
        reasons.append(f"Video metadata includes NRL signal: {', '.join(result_relevance[:3])}.")
    else:
        reasons.append("Surfaced by NRL-focused query, but video snippet has weak explicit NRL wording.")

    views = stats.get("views")
    if isinstance(views, int) and views >= 25_000:
        score += 0.1
        reasons.append(f"YouTube reports {views:,} views.")
    elif isinstance(views, int) and views >= 2_500:
        score += 0.06
        reasons.append(f"YouTube reports {views:,} views.")

    if stats.get("duration_seconds"):
        score += 0.03
        reasons.append("YouTube returned duration metadata for ingestion planning.")

    if seed.channel_id or stats.get("channel_id"):
        score += 0.04
        reasons.append("Parent YouTube channel ID is available for promotion linking.")

    if len(seed.signals) > 1:
        score += 0.03
        reasons.append(f"Found through {len(seed.signals)} deterministic signals.")

    if not result_relevance:
        score = min(score, 0.49)

    return _bounded_score(score), _ensure_two_reasons(reasons), categories


def _batch_channel_stats(channel_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(channel_ids), 50):
        for entry in youtube_api.get_channel_stats(list(channel_ids[i : i + 50])):
            channel_id = entry.get("channel_id")
            if channel_id:
                out[channel_id] = entry
    return out


def _draft_channel(seed: _ChannelSeed, stats: dict[str, Any]) -> CandidateDraft:
    score, reasons, categories = _score_channel(seed, stats)
    metadata = {
        "subscribers": stats.get("subs"),
        "video_count": stats.get("video_count"),
        "view_count": stats.get("view_count"),
        "country": stats.get("country"),
        "default_language": stats.get("default_language"),
        "published_at": stats.get("published_at"),
        "handle": stats.get("handle"),
        "logo_url": stats.get("avatar_url"),
        "uploads_playlist_id": stats.get("uploads_playlist_id"),
        "discovery_signals": seed.signals,
        "seed_context": seed.context,
    }
    metadata = {k: v for k, v in metadata.items() if v not in (None, "", [], {})}
    return CandidateDraft(
        kind="channel",
        external_id=seed.channel_id,
        url=f"https://www.youtube.com/channel/{seed.channel_id}",
        title=stats.get("title") or seed.title or seed.channel_id,
        description=stats.get("description") or seed.description or None,
        channel_external_id=None,
        content_categories=categories,
        score=score,
        score_reasons=reasons,
        metadata=metadata,
        discovered_via=_first_signal_summary(seed.signals),
    )


def _draft_video(seed: _VideoSeed, stats: dict[str, Any]) -> CandidateDraft:
    score, reasons, categories = _score_video(seed, stats)
    video_id = seed.video_id
    channel_id = stats.get("channel_id") or seed.channel_id or None
    metadata = {
        "channel_title": stats.get("channel_title") or seed.channel_title,
        "published_at": stats.get("published_at") or seed.published_at,
        "views": stats.get("views"),
        "likes": stats.get("likes"),
        "comments": stats.get("comments"),
        "duration_seconds": stats.get("duration_seconds"),
        "thumbnail_url": stats.get("thumbnail_url"),
        "tags": stats.get("tags"),
        "category_id": stats.get("category_id"),
        "is_live": stats.get("is_live"),
        "discovery_signals": seed.signals,
    }
    metadata = {k: v for k, v in metadata.items() if v not in (None, "", [], {})}
    return CandidateDraft(
        kind="video",
        external_id=video_id,
        url=seed.url or f"https://www.youtube.com/watch?v={video_id}",
        title=stats.get("title") or seed.title or video_id,
        description=stats.get("description") or seed.description or None,
        channel_external_id=channel_id,
        content_categories=categories,
        score=score,
        score_reasons=reasons,
        metadata=metadata,
        discovered_via=_first_signal_summary(seed.signals),
    )


def persist_candidate_drafts(
    session: Session,
    *,
    run_id: str,
    candidates: Sequence[CandidateDraft],
    dry_run: bool = False,
) -> PersistSummary:
    """Persist candidate drafts idempotently.

    Uses the existing uniqueness contract on ``(platform, kind, external_id)``.
    Duplicates should already be filtered before this function is called, but
    ``ON CONFLICT DO NOTHING`` keeps the write safe under concurrent runs.
    """

    if dry_run:
        return PersistSummary(inserted=0, duplicates=0, candidate_ids=[])

    inserted = 0
    duplicates = 0
    candidate_ids: list[str] = []
    for candidate in candidates:
        stmt = (
            pg_insert(MinerCandidate)
            .values(
                kind=candidate.kind,
                platform="youtube",
                external_id=candidate.external_id,
                url=candidate.url,
                title=candidate.title,
                description=candidate.description,
                channel_external_id=candidate.channel_external_id,
                content_categories=candidate.content_categories,
                score=candidate.score,
                score_reasons=candidate.score_reasons,
                metadata_json=candidate.metadata,
                discovered_via=candidate.discovered_via,
                status="pending",
                run_id=run_id,
            )
            .on_conflict_do_nothing(index_elements=["platform", "kind", "external_id"])
            .returning(MinerCandidate.id)
        )
        row = session.execute(stmt).first()
        if row is None:
            duplicates += 1
            continue
        inserted += 1
        candidate_ids.append(str(row[0]))
    session.commit()
    return PersistSummary(inserted=inserted, duplicates=duplicates, candidate_ids=candidate_ids)


def run_deterministic_youtube_discovery(
    session: Session,
    *,
    run_id: str,
    channel_queries: Sequence[str] | None = None,
    video_queries: Sequence[str] | None = None,
    harvest_queries: Sequence[str] | None = None,
    related_channel_ids: Sequence[str] | None = None,
    max_results_per_query: int = 10,
    max_videos_per_query: int = 25,
    published_after: str | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
    dry_run: bool = False,
) -> DeterministicYouTubeDiscoveryResult:
    """Run a deterministic YouTube source-discovery sweep."""

    cleaned_channel_queries = _clean_queries(channel_queries, DEFAULT_CHANNEL_QUERIES)
    cleaned_video_queries = _clean_queries(video_queries, DEFAULT_VIDEO_QUERIES)
    cleaned_harvest_queries = _clean_queries(harvest_queries, DEFAULT_HARVEST_QUERIES)
    cleaned_related_ids = [cid.strip() for cid in related_channel_ids or [] if cid and cid.strip()]
    channel_limit = max(1, min(max_results_per_query, 200))
    video_limit = max(1, min(max_videos_per_query, 200))
    harvest_limit = max(1, min(max_videos_per_query, 50))
    threshold = max(0.0, min(min_score, 1.0))

    known = load_known_youtube_ids(session)
    channel_seeds: dict[str, _ChannelSeed] = {}
    video_seeds: dict[str, _VideoSeed] = {}

    for query in cleaned_channel_queries:
        known_for_query = known.channel_ids | set(channel_seeds)
        for item in youtube_api.search_channels(
            query,
            max_results=channel_limit,
            filter_known_external_ids=known_for_query,
        ):
            _add_channel_seed(
                channel_seeds,
                channel_id=item.get("channel_id"),
                known_channel_ids=known.channel_ids,
                title=item.get("title", ""),
                description=item.get("description", ""),
                signal=_signal("channel_search", query),
            )

    for query in cleaned_harvest_queries:
        known_for_query = known.channel_ids | set(channel_seeds)
        for item in youtube_api.harvest_channels_from_videos(
            query,
            max_videos=harvest_limit,
            published_after=published_after,
            filter_known_external_ids=known_for_query,
        ):
            _add_channel_seed(
                channel_seeds,
                channel_id=item.get("channel_id"),
                known_channel_ids=known.channel_ids,
                title=item.get("channel_title", ""),
                signal=_signal("video_harvest", query),
                context={
                    "first_seen_video_title": item.get("first_seen_video_title"),
                    "first_seen_video_published_at": item.get("first_seen_video_published_at"),
                },
            )

    for channel_id in cleaned_related_ids:
        related_ids = youtube_api.get_channel_sections(channel_id)
        for related_id in related_ids:
            _add_channel_seed(
                channel_seeds,
                channel_id=related_id,
                known_channel_ids=known.channel_ids,
                signal=_signal("related_channels", related_to=channel_id),
            )

    for query in cleaned_video_queries:
        known_for_query = known.video_ids | set(video_seeds)
        for item in youtube_api.search_videos(
            query,
            max_results=video_limit,
            published_after=published_after,
            filter_known_external_ids=known_for_query,
        ):
            _add_video_seed(
                video_seeds,
                video_id=item.get("video_id"),
                known_video_ids=known.video_ids,
                channel_id=item.get("channel_id", ""),
                channel_title=item.get("channel_title", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                published_at=item.get("published_at", ""),
                url=item.get("url", ""),
                signal=_signal("video_search", query),
            )

    candidates: list[CandidateDraft] = []
    missing_metadata = 0
    below_threshold = 0

    channel_stats = _batch_channel_stats(list(channel_seeds))
    for seed in channel_seeds.values():
        stats = channel_stats.get(seed.channel_id)
        if not stats:
            missing_metadata += 1
            continue
        draft = _draft_channel(seed, stats)
        if draft.score < threshold:
            below_threshold += 1
            continue
        candidates.append(draft)

    video_stats = youtube_api.get_video_stats(list(video_seeds))
    for seed in video_seeds.values():
        stats = video_stats.get(seed.video_id)
        if not stats:
            missing_metadata += 1
            continue
        draft = _draft_video(seed, stats)
        if draft.score < threshold:
            below_threshold += 1
            continue
        candidates.append(draft)

    candidates.sort(key=lambda c: (c.score, c.kind, c.title.lower()), reverse=True)
    persist = persist_candidate_drafts(session, run_id=run_id, candidates=candidates, dry_run=dry_run)

    return DeterministicYouTubeDiscoveryResult(
        run_id=run_id,
        dry_run=dry_run,
        channel_queries=cleaned_channel_queries,
        video_queries=cleaned_video_queries,
        harvest_queries=cleaned_harvest_queries,
        related_channel_ids=cleaned_related_ids,
        known_channels_at_start=len(known.channel_ids),
        known_videos_at_start=len(known.video_ids),
        channel_seeds_seen=len(channel_seeds),
        video_seeds_seen=len(video_seeds),
        candidates_scored=len(channel_seeds) + len(video_seeds) - missing_metadata,
        candidates_below_threshold=below_threshold,
        candidates_missing_api_metadata=missing_metadata,
        candidates_inserted=persist.inserted,
        duplicates_skipped=persist.duplicates,
        candidate_ids=persist.candidate_ids,
        candidates=[candidate.to_public_dict() for candidate in candidates],
    )
