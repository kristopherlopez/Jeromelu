"""Voice + visual modality fusion — Phase 4 of speaker identification.

Combines per-turn voice matches (from `identify_voice`) and face matches
(from `visual_id`) into the final ``speaker_person_id`` assignment for
each ``source_speakers`` row. The provenance columns
(``audio_match_*`` / ``visual_match_*`` / ``match_method`` /
``match_confidence``) record both modalities so the review-UI override
(Phase 4b) can show why a turn was assigned.

Fusion table (per the plan in ``docs/todo/speaker-identification-plan.md``):

    voice match | face match | result
    -----------+------------+--------
    Person X   | Person X   | 'voice+face', high confidence, auto-assign
    Person X   | NULL       | 'voice', medium confidence, auto-assign
    NULL       | Person X   | 'face',  medium confidence, auto-assign
    Person X   | Person Y   | NULL — disagreement, flagged for review
    NULL       | NULL       | NULL — unknown

Disagreement falls through to NULL on purpose: when modalities conflict,
a single source has lied to us, and we don't know which. Phase 5
compounding will weight by historical accuracy and resolve some of these
automatically; for now they surface as unidentified turns for the
operator to review.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass
class FusedMatch:
    person_id: UUID
    method: str          # 'voice' | 'face' | 'voice+face'
    confidence: float    # 0..1, normalised across modalities


def fuse_per_turn(
    audio_person_id: UUID | None,
    audio_score: float | None,
    visual_person_id: UUID | None,
    visual_score: float | None,
) -> FusedMatch | None:
    """Combine voice + face matches into a single decision.

    Inputs come from ``identify_voice`` and ``visual_id``; either may be
    ``None`` when the modality didn't fire (no match, no enrolled
    embeddings, or input data missing).
    """
    voice_pid = audio_person_id
    face_pid = visual_person_id
    v_s = audio_score or 0.0
    f_s = visual_score or 0.0

    if voice_pid is None and face_pid is None:
        return None

    if voice_pid is not None and face_pid is not None:
        if voice_pid == face_pid:
            # Both modalities agree — average their scores. Voice cosine
            # (~0.7-0.99) and ArcFace cosine (~0.4-0.95) live on different
            # absolute scales; averaging is a coarse normaliser, but the
            # important property is that "both agree" reads as higher
            # confidence than either alone.
            return FusedMatch(
                person_id=voice_pid,
                method="voice+face",
                confidence=min(1.0, (v_s + f_s) / 2.0),
            )
        # Modalities disagree — refuse to commit.
        return None

    if voice_pid is not None:
        return FusedMatch(person_id=voice_pid, method="voice", confidence=v_s)

    return FusedMatch(person_id=face_pid, method="face", confidence=f_s)
