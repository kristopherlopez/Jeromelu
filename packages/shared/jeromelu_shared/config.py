from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_raw_bucket: str = "jeromelu-raw-transcripts"
    s3_clean_bucket: str = "jeromelu-clean-documents"
    s3_assets_bucket: str = "jeromelu-public-assets"
    openai_api_key: str = ""
    env: str = "development"
    admin_api_key: str = "local-dev-admin-key"
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "jeromelu"
    youtube_api_key: str = ""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
