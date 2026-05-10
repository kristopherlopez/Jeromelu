from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://jeromelu_admin:localdev123@localhost:5440/jeromelu"
    # Empty default = use real AWS S3 (the standard boto3 endpoint).
    # Local dev that wants MinIO sets S3_ENDPOINT explicitly via .env or
    # shell; docker-compose.yml does so for the dev stack. Phase 5.5 fix:
    # SageMaker silently drops empty-string env values, so we can't rely
    # on `S3_ENDPOINT=""` overriding a localhost default in the GPU
    # container — the default itself has to be empty.
    s3_endpoint: str = ""
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_raw_bucket: str = "jeromelu-raw-transcripts"
    s3_audio_bucket: str = "jeromelu-raw-audio"
    s3_clean_bucket: str = "jeromelu-clean-documents"
    s3_assets_bucket: str = "jeromelu-public-assets"
    s3_player_data_bucket: str = "jeromelu-player-data"
    s3_agent_logs_bucket: str = "jeromelu-clean-documents"
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    llm_provider: str = "openai"  # "openai" or "openrouter"
    llm_model: str = "gpt-4o"  # model ID for chat completions
    env: str = "development"
    cdn_base_url: str = ""  # empty for local dev; in prod: "https://jeromelu.ai"
    admin_api_key: str = "local-dev-admin-key"
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "jeromelu"
    youtube_api_key: str = ""
    webshare_proxy_username: str = ""
    webshare_proxy_password: str = ""
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"
    huggingface_api_key: str = ""  # required for pyannote (gated model)
    pyannote_model: str = "pyannote/speaker-diarization-3.1"

    # Phase 5.5 — Lineup on SageMaker Async. When `lineup_remote` is true,
    # diarize.py / visual_id.py dispatch to the remote endpoint instead
    # of running ML inference locally. Defaults off so dev without
    # GPU/AWS still works.
    lineup_remote: bool = False
    lineup_endpoint_name: str = "jeromelu-lineup-async"
    # us-east-1 not ap-southeast-2: Sydney g4dn / g5 capacity was
    # exhausted at deploy time. us-east-1 has effectively unlimited GPU
    # capacity. Cross-region S3 reads to the Sydney buckets cost
    # ~$0.001/source — rounding error against per-source GPU compute.
    lineup_aws_region: str = "us-east-1"
    lineup_ecr_repo: str = "jeromelu/lineup-gpu"
    lineup_sagemaker_role_arn: str = ""  # arn:aws:iam::ACCOUNT:role/JeromeluSagemakerLineup
    # SageMaker Async requires its input + output S3 paths to be in the
    # same region as the endpoint. Audio/transcripts live in Sydney; the
    # endpoint runs in us-east-1 (capacity). Staging bucket bridges that
    # — it only carries invoke request/response JSONs (small, ephemeral).
    # Container code still reads/writes the actual artefacts cross-region
    # to the Sydney buckets, which works fine via virtual-host boto3.
    lineup_staging_bucket: str = "jeromelu-sagemaker-async"
    lineup_input_prefix: str = "input"
    lineup_output_prefix: str = "output"

    # Video worker (services/video-worker) — sidecar container in the
    # compose stack that runs yt-dlp + ffmpeg out of the API image. Per
    # feedback_api_container_lean.md, the API container does not ship
    # those deps; the worker is reachable via docker DNS. In dev / unit
    # tests the worker isn't running and callers should branch on the
    # ConnectError or stub the client.
    video_worker_url: str = "http://video-worker:8000"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
