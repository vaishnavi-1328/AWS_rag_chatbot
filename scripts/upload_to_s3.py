#!/usr/bin/env python3
"""
Upload FAISS index and documents to S3.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.s3 import S3Client
from src.utils.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Upload data to S3")
    parser.add_argument(
        "--index",
        type=str,
        default="data/index/faiss_index.faiss",
        help="Path to FAISS index file",
    )
    parser.add_argument(
        "--documents",
        type=str,
        default="data/processed/documents.json",
        help="Path to documents JSON file",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=None,
        help="S3 bucket name (default from config)",
    )
    parser.add_argument(
        "--create-bucket",
        action="store_true",
        help="Create bucket if it doesn't exist",
    )

    args = parser.parse_args()

    bucket = args.bucket or settings.s3_bucket_name
    index_path = Path(args.index)
    documents_path = Path(args.documents)

    # Initialize S3 client
    s3 = S3Client(bucket_name=bucket)

    # Create bucket if requested
    if args.create_bucket:
        try:
            import boto3
            client = boto3.client('s3', region_name=settings.aws_region)
            client.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={'LocationConstraint': settings.aws_region}
                if settings.aws_region != 'us-east-1' else {}
            )
            logger.info(f"Created bucket: {bucket}")
        except Exception as e:
            logger.warning(f"Could not create bucket (may already exist): {e}")

    # Upload FAISS index
    if index_path.exists():
        s3.upload_file(str(index_path), settings.s3_faiss_key)
        logger.info(f"Uploaded index: {settings.s3_faiss_key}")
    else:
        logger.warning(f"Index file not found: {index_path}")

    # Upload documents
    if documents_path.exists():
        s3.upload_file(str(documents_path), f"{settings.s3_data_prefix}documents.json")
        logger.info(f"Uploaded documents: {settings.s3_data_prefix}documents.json")
    else:
        logger.warning(f"Documents file not found: {documents_path}")

    logger.info("Upload complete!")


if __name__ == "__main__":
    main()
