"""
Configuration management for NHTSA Recall Analyzer.
Loads settings from environment variables with sensible defaults.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS Configuration
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_profile: Optional[str] = Field(default=None, alias="AWS_PROFILE")

    # S3 Configuration
    s3_bucket_name: str = Field(default="nhtsa-recall-analyzer", alias="S3_BUCKET_NAME")
    s3_faiss_key: str = Field(default="index/faiss_index.pkl", alias="S3_FAISS_KEY")
    s3_data_prefix: str = Field(default="data/", alias="S3_DATA_PREFIX")

    # Bedrock Configuration
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-haiku-20240307-v1:0",
        alias="BEDROCK_MODEL_ID"
    )
    bedrock_embedding_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        alias="BEDROCK_EMBEDDING_MODEL_ID"
    )

    # API Configuration
    api_gateway_url: Optional[str] = Field(default=None, alias="API_GATEWAY_URL")

    # Application Settings
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_documents_to_retrieve: int = Field(default=10, alias="MAX_DOCUMENTS_TO_RETRIEVE")
    relevance_threshold: float = Field(default=0.7, alias="RELEVANCE_THRESHOLD")

    # LLM Settings
    max_tokens: int = Field(default=1024, alias="MAX_TOKENS")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
