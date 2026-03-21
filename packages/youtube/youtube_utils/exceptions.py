class RateLimitError(Exception):
    """Raised when YouTube rate-limits a request."""


class NoTranscriptAvailable(Exception):
    """Raised when a video has no transcript (disabled or not found)."""


class DownloadError(Exception):
    """Raised when yt-dlp fails to download media."""


class SearchError(Exception):
    """Raised when YouTube API channel search fails."""
