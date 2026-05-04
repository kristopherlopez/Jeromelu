from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://jeromelu_admin:localdev123@localhost:5440/jeromelu"
    s3_endpoint: str = "http://localhost:9000"
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
    lineup_aws_region: str = "ap-southeast-2"
    lineup_ecr_repo: str = "jeromelu/lineup-gpu"
    lineup_sagemaker_role_arn: str = ""  # arn:aws:iam::ACCOUNT:role/JeromeluSagemakerLineup
    lineup_input_prefix: str = "sagemaker/lineup/input"
    lineup_output_prefix: str = "sagemaker/lineup/output"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
