"""
AWS Bedrock client wrapper for Claude and Titan models.
Provides unified interface for LLM and embedding calls.
"""

import json
import logging
from typing import Any, Optional

import boto3
from botocore.config import Config

from .config import settings

logger = logging.getLogger(__name__)


class BedrockClient:
    """Wrapper for AWS Bedrock API calls."""

    def __init__(
        self,
        region: Optional[str] = None,
        model_id: Optional[str] = None,
        embedding_model_id: Optional[str] = None,
    ):
        self.region = region or settings.aws_region
        self.model_id = model_id or settings.bedrock_model_id
        self.embedding_model_id = embedding_model_id or settings.bedrock_embedding_model_id

        # Configure boto3 with retries
        config = Config(
            region_name=self.region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        self.client = boto3.client("bedrock-runtime", config=config)
        logger.info(f"Initialized Bedrock client in {self.region}")

    def invoke_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        """
        Invoke Claude model via Bedrock.

        Args:
            prompt: User message/prompt
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Returns:
            Model response text
        """
        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except Exception as e:
            logger.error(f"Error invoking Claude: {e}")
            raise

    def get_embeddings(self, text: str) -> list[float]:
        """
        Generate embeddings using Titan Embeddings model.

        Args:
            text: Text to embed

        Returns:
            List of embedding floats
        """
        body = {
            "inputText": text,
        }

        try:
            response = self.client.invoke_model(
                modelId=self.embedding_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            return response_body["embedding"]

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            embedding = self.get_embeddings(text)
            embeddings.append(embedding)
        return embeddings


# Singleton instance for reuse
_bedrock_client: Optional[BedrockClient] = None


def get_bedrock_client() -> BedrockClient:
    """Get or create Bedrock client singleton."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockClient()
    return _bedrock_client
