# youtube-utils

Reusable Python utilities for YouTube: transcripts, discovery, and media downloads.

## Install

```bash
pip install path/to/packages/youtube
# or editable
pip install -e packages/youtube
# or from git
pip install "youtube-utils @ git+https://github.com/you/repo#subdirectory=packages/youtube"
```

**Requires:** Python 3.12+, ffmpeg (for audio conversion)

## Usage

### Fetch transcript

```python
from youtube_utils import fetch_transcript

segments = fetch_transcript("dQw4w9WgXcQ")
# [{"start": 0.0, "end": 2.5, "text": "...", "speaker": None}, ...]

# With proxy
segments = fetch_transcript("dQw4w9WgXcQ", proxy={
    "username": "user",
    "password": "pass",
})
```

### Discover channel videos

```python
from youtube_utils import list_channel_videos

videos = list_channel_videos("UC_x5XG1OV2P6uZZ5FSM9Ttw", max_results=10)
# [{"video_id": "abc123", "title": "...", "published_at": "2026-03-01T00:00:00Z"}, ...]
```

Tries RSS first (fast, free), falls back to yt-dlp.

### Search for channels by topic

```python
from youtube_utils import search_channels

channels = search_channels("NRL supercoach", max_results=5)
# [{"channel_id": "UC...", "title": "...", "channel_url": "https://..."}, ...]

for ch in channels:
    print(f"{ch['title']} — {ch['channel_id']}")
```

No API key needed — uses yt-dlp to search videos and extract unique channels.

### Download audio

```python
from youtube_utils import download_audio

path = download_audio("dQw4w9WgXcQ", output_dir="./downloads", format="mp3")
# Path('downloads/Rick Astley - Never Gonna Give You Up.mp3')
```

### Download video

```python
from youtube_utils import download_video

path = download_video("dQw4w9WgXcQ", output_dir="./downloads")
# Path('downloads/Rick Astley - Never Gonna Give You Up.mp4')

# Specific quality
path = download_video("dQw4w9WgXcQ", quality="720")
```

## API

| Function | Args | Returns |
|----------|------|---------|
| `fetch_transcript(video_id, proxy=None)` | `video_id`: str, `proxy`: dict with `username`/`password` | `list[dict]` with `start`, `end`, `text`, `speaker` |
| `list_channel_videos(channel_id, max_results=15)` | `channel_id`: str | `list[dict]` with `video_id`, `title`, `published_at` |
| `search_channels(query, max_results=10)` | `query`: str | `list[dict]` with `channel_id`, `title`, `channel_url` |
| `download_audio(video_id_or_url, output_dir=".", format="mp3")` | ID or full URL | `Path` to downloaded file |
| `download_video(video_id_or_url, output_dir=".", format="mp4", quality="best")` | ID or full URL, quality: `"best"`, `"worst"`, or height like `"720"` | `Path` to downloaded file |

## Exceptions

| Exception | When |
|-----------|------|
| `NoTranscriptAvailable` | Video has no captions |
| `RateLimitError` | YouTube rate-limited the request |
| `DownloadError` | yt-dlp failed to download |
| `SearchError` | Channel search failed |

```python
from youtube_utils.exceptions import NoTranscriptAvailable, RateLimitError, DownloadError, SearchError
```
