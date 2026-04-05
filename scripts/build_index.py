#!/usr/bin/env python3
"""
Build FAISS index from processed NHTSA documents.

This script:
1. Loads processed documents
2. Generates embeddings using Bedrock Titan
3. Builds FAISS index
4. Saves index for deployment
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup
import faiss

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_documents(documents_path: Path) -> list[dict]:
    """Load processed documents."""
    logger.info(f"Loading documents from {documents_path}")
    with open(documents_path, 'r', encoding='utf-8') as f:
        documents = json.load(f)
    logger.info(f"Loaded {len(documents)} documents")
    return documents


def get_embedding_dimension() -> int:
    """Get the embedding dimension from Titan model."""
    # Titan Text Embeddings v2 produces 1024-dimensional vectors
    return 1024


def generate_embeddings_bedrock(texts: list[str], batch_size: int = 10) -> np.ndarray:
    """Generate embeddings using AWS Bedrock Titan."""
    from src.utils.bedrock import get_bedrock_client

    client = get_bedrock_client()
    embeddings = []

    logger.info(f"Generating embeddings for {len(texts)} texts...")

    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
        batch = texts[i:i + batch_size]
        for text in batch:
            try:
                embedding = client.get_embeddings(text[:8000])  # Titan has token limits
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Error embedding text: {e}")
                # Use zero vector as fallback
                embeddings.append([0.0] * get_embedding_dimension())

    return np.array(embeddings, dtype=np.float32)


def generate_embeddings_mock(texts: list[str]) -> np.ndarray:
    """Generate mock embeddings for testing without AWS."""
    logger.info(f"Generating MOCK embeddings for {len(texts)} texts...")
    dim = get_embedding_dimension()

    # Use a simple hash-based approach for deterministic mock embeddings
    embeddings = []
    for text in tqdm(texts, desc="Mock embedding"):
        # Create a pseudo-random embedding based on text content
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(dim).astype(np.float32)
        # Normalize
        embedding = embedding / np.linalg.norm(embedding)
        embeddings.append(embedding)

    return np.array(embeddings, dtype=np.float32)


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """Build FAISS index from embeddings."""
    dim = embeddings.shape[1]
    n_vectors = embeddings.shape[0]

    logger.info(f"Building FAISS index: {n_vectors} vectors, {dim} dimensions")

    # For small datasets, use flat index (exact search)
    # For larger datasets, could use IVF or HNSW
    if n_vectors < 10000:
        # Flat index - exact search, good for small datasets
        index = faiss.IndexFlatIP(dim)  # Inner product (cosine similarity after normalization)

        # Normalize vectors for cosine similarity
        faiss.normalize_L2(embeddings)

        index.add(embeddings)
    else:
        # IVF index for larger datasets
        nlist = min(100, n_vectors // 10)  # Number of clusters
        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)

        # Normalize vectors
        faiss.normalize_L2(embeddings)

        # Train and add
        index.train(embeddings)
        index.add(embeddings)

    logger.info(f"Index built with {index.ntotal} vectors")
    return index


def save_index(index: faiss.Index, output_path: Path) -> None:
    """Save FAISS index to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_path))
    logger.info(f"Saved index to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Build FAISS index from documents")
    parser.add_argument(
        "--documents",
        type=str,
        default="data/processed/documents.json",
        help="Path to processed documents JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/index/faiss_index.faiss",
        help="Output path for FAISS index",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock embeddings (no AWS calls)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for embedding generation",
    )

    args = parser.parse_args()

    documents_path = Path(args.documents)
    output_path = Path(args.output)

    # Check if documents exist
    if not documents_path.exists():
        # Try sample data
        sample_path = Path("data/sample/sample_recalls.json")
        if sample_path.exists():
            logger.info("Documents not found, using sample data...")
            # Create processed documents from sample
            from scripts.process_data import DocumentProcessor
            processor = DocumentProcessor()
            documents = processor.load_and_process(sample_path.parent.parent / "raw")

            if not documents:
                # Load sample directly
                with open(sample_path, 'r') as f:
                    sample_recalls = json.load(f)
                sample_complaints_path = Path("data/sample/sample_complaints.json")
                sample_complaints = []
                if sample_complaints_path.exists():
                    with open(sample_complaints_path, 'r') as f:
                        sample_complaints = json.load(f)

                documents = []
                for recall in sample_recalls:
                    documents.append(processor.process_recall(recall))
                for complaint in sample_complaints:
                    documents.append(processor.process_complaint(complaint))

            # Save processed documents
            documents_path.parent.mkdir(parents=True, exist_ok=True)
            with open(documents_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, indent=2)
            logger.info(f"Created {documents_path} from sample data")
        else:
            logger.error(f"Documents not found: {documents_path}")
            logger.error("Run scripts/fetch_nhtsa_data.py and scripts/process_data.py first")
            sys.exit(1)

    # Load documents
    documents = load_documents(documents_path)

    if not documents:
        logger.error("No documents to index!")
        sys.exit(1)

    # Extract text for embedding
    texts = [doc.get('text', doc.get('summary', '')) for doc in documents]

    # Generate embeddings
    if args.mock:
        embeddings = generate_embeddings_mock(texts)
    else:
        try:
            embeddings = generate_embeddings_bedrock(texts, args.batch_size)
        except Exception as e:
            logger.error(f"Failed to generate embeddings with Bedrock: {e}")
            logger.info("Falling back to mock embeddings...")
            embeddings = generate_embeddings_mock(texts)

    # Build index
    index = build_faiss_index(embeddings)

    # Save index
    save_index(index, output_path)

    # Verify
    logger.info(f"\nIndex Statistics:")
    logger.info(f"  Total vectors: {index.ntotal}")
    logger.info(f"  Dimensions: {embeddings.shape[1]}")
    logger.info(f"  Index size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Test search
    logger.info("\nTesting search...")
    query_text = "engine stall fuel pump"
    if args.mock:
        np.random.seed(hash(query_text) % (2**32))
        query_embedding = np.random.randn(1, get_embedding_dimension()).astype(np.float32)
        faiss.normalize_L2(query_embedding)
    else:
        from src.utils.bedrock import get_bedrock_client
        client = get_bedrock_client()
        query_embedding = np.array([client.get_embeddings(query_text)], dtype=np.float32)
        faiss.normalize_L2(query_embedding)

    distances, indices = index.search(query_embedding, 3)

    logger.info(f"Test query: '{query_text}'")
    logger.info("Top 3 results:")
    for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx >= 0 and idx < len(documents):
            doc = documents[idx]
            logger.info(f"  {i+1}. {doc.get('type', 'unknown')}: {doc.get('subject', doc.get('id', 'N/A'))[:50]}... (score: {dist:.3f})")


if __name__ == "__main__":
    main()
