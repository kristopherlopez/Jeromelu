"""Cross-version compatibility shim for pyannote.audio 3.x ↔ 4.x.

pyannote 3.x exposes ``Pipeline.from_pretrained(name, use_auth_token=...)``.
pyannote 4.x renamed the kwarg to ``token=`` and the 3.x kwarg is gone
(strict signatures — passing the old name raises ``TypeError`` immediately).

The runtime split exists because the local dev environment is pinned to
3.4 (avoids the torchcodec + FFmpeg-shared-libs setup pyannote 4 requires
on Windows), while the SageMaker container ships 4.x for community-1
support. Both code paths share the same analyst modules — this shim
lets a single call site work in either.

If we ever drop the 3.x local-dev path, the shim collapses to a single
``token=`` keyword and this module disappears.
"""

from __future__ import annotations


def _major_version() -> int:
    """Return the major version of the installed pyannote.audio (e.g. 3 or 4)."""
    import pyannote.audio

    # Versions like "4.0.4" or "3.4.0" — split on dot, parse first segment.
    raw = pyannote.audio.__version__.split(".")[0]
    try:
        return int(raw)
    except ValueError:
        # Unknown / dev builds default to the modern API, which matches
        # where the project is heading and fails loud if it's wrong.
        return 4


def token_kwargs(hf_token: str | None) -> dict:
    """Return a kwargs dict carrying the HF token under the right name
    for the installed pyannote.audio version.

    Use at every ``Pipeline.from_pretrained`` / ``Model.from_pretrained``
    call site::

        Pipeline.from_pretrained(name, **token_kwargs(settings.huggingface_api_key))
    """
    if not hf_token:
        return {}
    return {"token": hf_token} if _major_version() >= 4 else {"use_auth_token": hf_token}
