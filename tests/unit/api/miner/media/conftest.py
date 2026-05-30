"""Stub the youtube acquisition stack for the media-acquisition unit tests.

``app.miner.media.audio`` and ``app.miner.media.persistent_video`` import
``youtube_utils`` and ``yt_dlp`` at module level — they wrap yt-dlp for the
real downloads. That stack is a first-party isolated dependency
(``packages/youtube``, shipped only to the video-worker) and is deliberately
absent from the lean unit-test tier (see ``requirements-test.txt``). Without a
stub, importing those modules aborts collection with ``ModuleNotFoundError``
and takes the whole ``tests/unit`` suite down with it.

These tests monkeypatch every real download call, so the genuine packages are
never exercised. We register minimal stand-ins in ``sys.modules`` before the
test module's ``from youtube_utils... import ...`` lines resolve. The one
symbol that must be a shared, real type is ``DownloadError``: ``acquire_audio``
catches it and the test raises it, so both sides must bind the same class —
which they do, since both import it from the stub installed here.
"""

from __future__ import annotations

import sys
import types


def _install_youtube_stubs() -> None:
    """Register lightweight youtube_utils / yt_dlp stand-ins for the lean tier.

    No-ops if the real packages are already imported, so a fuller local
    environment keeps using them.
    """
    if "youtube_utils" not in sys.modules:
        youtube_utils = types.ModuleType("youtube_utils")
        exceptions = types.ModuleType("youtube_utils.exceptions")

        class DownloadError(Exception):
            """Stand-in for ``youtube_utils.exceptions.DownloadError``."""

        def download_audio(*_args, **_kwargs):  # pragma: no cover - always patched
            raise RuntimeError("youtube_utils.download_audio stub called; monkeypatch it in the test")

        exceptions.DownloadError = DownloadError
        youtube_utils.exceptions = exceptions
        youtube_utils.download_audio = download_audio
        sys.modules["youtube_utils"] = youtube_utils
        sys.modules["youtube_utils.exceptions"] = exceptions

    sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))


_install_youtube_stubs()
