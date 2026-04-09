from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://jeromelu_admin:localdev123@localhost:5440/jeromelu"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_raw_bucket: str = "jeromelu-raw-transcripts"
    s3_clean_bucket: str = "jeromelu-clean-documents"
    s3_assets_bucket: str = "jeromelu-public-assets"
    s3_player_data_bucket: str = "jeromelu-player-data"
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

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
