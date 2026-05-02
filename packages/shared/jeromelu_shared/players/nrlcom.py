"""Fetch player profile data from nrl.com.

Each player profile page (``/players/nrl-premiership/{team_short}/{slug}/``)
embeds a ``<script type="application/ld+json">`` block with schema.org
``Person`` data: name, dob, birth place, image, height, weight, jobTitle.

This module fetches one player at a time and parses that JSON-LD into a
:class:`NrlProfile`. The refresh function in
:mod:`jeromelu_shared.players.nrlcom_refresh` walks the existing
``people`` rows and calls this for each.

URL slug derivation: ``slugify(canonical_name)`` (lowercase + spaces→hyphens,
hyphens preserved) plus ``team.short_name.lower()``. This matches all but
~5–10% of names; per-person overrides on
``people.metadata_json.nrlcom`` handle the misses (apostrophes, accents,
recently-traded players whose nrl.com profile is still on the old club).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


PROFILE_URL = "https://www.nrl.com/players/nrl-premiership/{team_short}/{slug}/"
USER_AGENT = "Mozilla/5.0 (compatible; jeromelu-roster/1.0)"

_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL,
)


@dataclass
class NrlProfile:
    """Subset of the JSON-LD ``Person`` block we promote into the DB."""
    canonical_name: str
    dob: date | None
    birthplace_text: str | None     # raw e.g. "Sydney, NSW" — no normalisation in v1
    image_url: str | None
    height_cm: int | None
    weight_kg: int | None
    job_title: str | None           # raw e.g. "Captain - Halfback" — captaincy ignored


_APOSTROPHE_OR_DOT_RE = re.compile(r"[\.‘’']")
_WHITESPACE_RE = re.compile(r"\s+")


def slugify_name(name: str) -> str:
    """Match nrl.com's slug rule.

    Verified empirically against the live league:
      - lowercase
      - Unicode-fold accents to ASCII (``ä → a``, ``ñ → n``)
      - strip apostrophes (straight and typographic) and dots
      - whitespace → hyphens
      - existing hyphens are preserved (``Fonua-Blake → fonua-blake``)

    Censored names (``Jack *** Bird`` in the SC source) and other
    non-letter punctuation will produce nonsense slugs — those need
    per-person overrides on ``people.metadata_json.nrlcom.slug``.
    """
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = _APOSTROPHE_OR_DOT_RE.sub("", folded.strip().lower())
    s = _WHITESPACE_RE.sub("-", s)
    return s


# nrl.com mostly uses the bare nickname (`broncos`, `sharks`, ...), but
# two clubs keep the full prefix in their URL slugs. Verified empirically
# against the live league — see comments in
# `docs/agents/system/player-roster.md`.
NRLCOM_TEAM_OVERRIDES: dict[str, str] = {
    "tigers":    "wests-tigers",
    "rabbitohs": "south-sydney-rabbitohs",
}


def slugify_team_short(team_short: str) -> str:
    """nrl.com URL form for ``Team.short_name``.

    Default rule: lowercase + spaces→hyphens (``Sea Eagles → sea-eagles``).
    Two clubs need a hardcoded override (Wests Tigers, South Sydney
    Rabbitohs) — see ``NRLCOM_TEAM_OVERRIDES``.
    """
    base = team_short.strip().lower().replace(" ", "-")
    return NRLCOM_TEAM_OVERRIDES.get(base, base)


def resolve_profile_url(
    canonical_name: str,
    team_short: str,
    *,
    override_slug: str | None = None,
    override_team_short: str | None = None,
) -> str:
    """Build the profile URL, preferring per-person overrides when supplied."""
    return PROFILE_URL.format(
        team_short=slugify_team_short(override_team_short or team_short),
        slug=override_slug or slugify_name(canonical_name),
    )


def fetch_profile(
    canonical_name: str,
    team_short: str,
    *,
    client: httpx.Client | None = None,
    override_slug: str | None = None,
    override_team_short: str | None = None,
    timeout: float = 15.0,
) -> tuple[NrlProfile | None, str]:
    """Fetch + parse one player's nrl.com profile JSON-LD.

    Returns ``(profile, url)``. ``profile`` is ``None`` on 404 (the URL
    is still returned so the caller can record what was tried). Other
    HTTP errors raise via ``raise_for_status``.
    """
    url = resolve_profile_url(
        canonical_name,
        team_short,
        override_slug=override_slug,
        override_team_short=override_team_short,
    )
    owns_client = client is None
    if client is None:
        client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout)
    try:
        r = client.get(url)
        if r.status_code == 404:
            return None, url
        r.raise_for_status()
        return _parse_jsonld(r.text), url
    finally:
        if owns_client:
            client.close()


def _parse_jsonld(html: str) -> NrlProfile | None:
    m = _JSONLD_RE.search(html)
    if not m:
        return None
    d = json.loads(m.group(1))
    if d.get("@type") != "Person":
        return None

    dob = None
    if isinstance(d.get("birthDate"), str) and d["birthDate"]:
        # ISO datetime; we only need the date part
        try:
            dob = date.fromisoformat(d["birthDate"][:10])
        except ValueError:
            dob = None

    bp = (d.get("birthPlace") or {}).get("address")
    birthplace_text = bp.strip() if isinstance(bp, str) and bp.strip() else None

    return NrlProfile(
        canonical_name=d.get("name") or "",
        dob=dob,
        birthplace_text=birthplace_text,
        image_url=((d.get("image") or {}).get("url")) or None,
        height_cm=_qv(d.get("height"), expected_unit="CMT"),
        weight_kg=_qv(d.get("weight"), expected_unit="KGM"),
        job_title=d.get("jobTitle") or None,
    )


def _qv(node: Any, *, expected_unit: str) -> int | None:
    """Extract an integer cm/kg value from a schema.org QuantitativeValue."""
    if not isinstance(node, dict):
        return None
    if node.get("unitCode") != expected_unit:
        return None
    v = node.get("value")
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None
