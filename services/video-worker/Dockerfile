FROM python:3.12-slim

# ffmpeg is the only system dep — used for single-frame extraction.
# Pinned to whatever Debian bookworm ships; we don't need a specific
# version since we only call ffmpeg with stable basic flags.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/video-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/video-worker/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
