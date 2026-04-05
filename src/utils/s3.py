"""
S3 utilities for uploading/downloading FAISS index and data files.
"""

import json
import logging
import pickle
from io import BytesIO
from typing import Any, Optional

import boto3
from botocore.config import Config

from .config import settings

logger = logging.getLogger(__name__)


class S3Client:
    """Wrapper for S3 operations."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or settings.s3_bucket_name
        self.region = region or settings.aws_region

        config = Config(
            region_name=self.region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        self.client = boto3.client("s3", config=config)
        logger.info(f"Initialized S3 client for bucket: {self.bucket_name}")

    def upload_json(self, data: Any, key: str) -> None:
        """Upload JSON data to S3."""
        try:
            body = json.dumps(data, indent=2, ensure_ascii=False)
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"Uploaded JSON to s3://{self.bucket_name}/{key}")
        except Exception as e:
            logger.error(f"Error uploading JSON to S3: {e}")
            raise

    def download_json(self, key: str) -> Any:
        """Download and parse JSON from S3."""
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error downloading JSON from S3: {e}")
            raise

    def upload_pickle(self, obj: Any, key: str) -> None:
        """Upload pickled object to S3 (for FAISS index)."""
        try:
            buffer = BytesIO()
            pickle.dump(obj, buffer)
            buffer.seek(0)

            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=buffer.getvalue(),
                ContentType="application/octet-stream",
            )
            logger.info(f"Uploaded pickle to s3://{self.bucket_name}/{key}")
        except Exception as e:
            logger.error(f"Error uploading pickle to S3: {e}")
            raise

    def download_pickle(self, key: str) -> Any:
        """Download and unpickle object from S3."""
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            content = response["Body"].read()
            return pickle.loads(content)
        except Exception as e:
            logger.error(f"Error downloading pickle from S3: {e}")
            raise

    def upload_file(self, local_path: str, key: str) -> None:
        """Upload a local file to S3."""
        try:
            self.client.upload_file(local_path, self.bucket_name, key)
            logger.info(f"Uploaded {local_path} to s3://{self.bucket_name}/{key}")
        except Exception as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise

    def download_file(self, key: str, local_path: str) -> None:
        """Download a file from S3 to local path."""
        try:
            self.client.download_file(self.bucket_name, key, local_path)
            logger.info(f"Downloaded s3://{self.bucket_name}/{key} to {local_path}")
        except Exception as e:
            logger.error(f"Error downloading file from S3: {e}")
            raise

    def list_objects(self, prefix: str = "") -> list[str]:
        """List objects in bucket with optional prefix."""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
            )
            return [obj["Key"] for obj in response.get("Contents", [])]
        except Exception as e:
            logger.error(f"Error listing S3 objects: {e}")
            raise

    def object_exists(self, key: str) -> bool:
        """Check if an object exists in S3."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False


# Singleton instance
_s3_client: Optional[S3Client] = None


def get_s3_client() -> S3Client:
    """Get or create S3 client singleton."""
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client
