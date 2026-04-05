"""
Retriever Agent - Performs FAISS similarity search on NHTSA documents.

Loads the FAISS index from S3 and retrieves relevant documents
based on the user query and vehicle information.
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from ..graph.state import Document, GraphState
from ..utils.bedrock import get_bedrock_client
from ..utils.config import settings
from ..utils.s3 import get_s3_client

logger = logging.getLogger(__name__)

# Global cache for FAISS index (Lambda reuses between invocations)
_faiss_index = None
_documents_cache = None


class FAISSRetriever:
    """FAISS-based document retriever."""

    def __init__(
        self,
        index_path: Optional[str] = None,
        documents_path: Optional[str] = None,
    ):
        self.index = None
        self.documents = []
        self.embeddings_client = get_bedrock_client()

        # Load from provided paths or defaults
        if index_path and documents_path:
            self.load_local(index_path, documents_path)

    def load_local(self, index_path: str, documents_path: str) -> None:
        """Load FAISS index and documents from local files."""
        import faiss

        logger.info(f"Loading FAISS index from {index_path}")
        self.index = faiss.read_index(index_path)

        logger.info(f"Loading documents from {documents_path}")
        with open(documents_path, 'r', encoding='utf-8') as f:
            self.documents = json.load(f)

        logger.info(f"Loaded {self.index.ntotal} vectors, {len(self.documents)} documents")

    def load_from_s3(self, bucket: str, index_key: str, documents_key: str) -> None:
        """Load FAISS index and documents from S3."""
        import faiss
        import tempfile

        s3 = get_s3_client()

        # Download index to temp file
        with tempfile.NamedTemporaryFile(suffix='.faiss', delete=False) as tmp:
            s3.download_file(index_key, tmp.name)
            self.index = faiss.read_index(tmp.name)

        # Download documents
        self.documents = s3.download_json(documents_key)

        logger.info(f"Loaded from S3: {self.index.ntotal} vectors, {len(self.documents)} documents")

    def get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for query text."""
        embedding = self.embeddings_client.get_embeddings(text)
        return np.array(embedding, dtype=np.float32)

    def search(
        self,
        query: str,
        k: int = 10,
        filter_types: Optional[list[str]] = None,
        filter_vehicle: Optional[dict] = None,
    ) -> list[tuple[dict, float]]:
        """
        Search for relevant documents.

        Args:
            query: Search query text
            k: Number of results to return
            filter_types: Filter by document types (recall, complaint)
            filter_vehicle: Filter by vehicle info (make, model, year)

        Returns:
            List of (document, score) tuples
        """
        if self.index is None:
            raise ValueError("Index not loaded. Call load_local() or load_from_s3() first.")

        # Get query embedding
        query_embedding = self.get_embedding(query)
        query_embedding = query_embedding.reshape(1, -1)

        # Search more than needed to allow for filtering
        search_k = min(k * 5, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, search_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for empty slots
                continue

            doc = self.documents[idx]
            score = float(1 / (1 + dist))  # Convert distance to similarity score

            # Apply filters
            if filter_types and doc.get('type') not in filter_types:
                continue

            if filter_vehicle:
                doc_vehicle = doc.get('vehicle', {})
                # Check make (case-insensitive)
                if filter_vehicle.get('make'):
                    if doc_vehicle.get('make', '').lower() != filter_vehicle['make'].lower():
                        continue
                # Check model (case-insensitive, partial match)
                if filter_vehicle.get('model'):
                    doc_model = doc_vehicle.get('model', '').lower()
                    query_model = filter_vehicle['model'].lower()
                    if query_model not in doc_model and doc_model not in query_model:
                        continue
                # Check year (exact match or within range)
                if filter_vehicle.get('year'):
                    doc_year = doc_vehicle.get('year', 0)
                    query_year = filter_vehicle['year']
                    if abs(doc_year - query_year) > 2:  # Allow 2 year tolerance
                        continue

            results.append((doc, score))

            if len(results) >= k:
                break

        return results


def get_retriever() -> FAISSRetriever:
    """Get or create retriever instance with cached index."""
    global _faiss_index, _documents_cache

    retriever = FAISSRetriever()

    # Try to use cached index
    if _faiss_index is not None and _documents_cache is not None:
        retriever.index = _faiss_index
        retriever.documents = _documents_cache
        return retriever

    # Try to load from local files first (for development)
    local_index = Path('data/index/faiss_index.faiss')
    local_docs = Path('data/processed/documents.json')

    if local_index.exists() and local_docs.exists():
        retriever.load_local(str(local_index), str(local_docs))
        _faiss_index = retriever.index
        _documents_cache = retriever.documents
        return retriever

    # Try S3 (for Lambda deployment)
    try:
        retriever.load_from_s3(
            bucket=settings.s3_bucket_name,
            index_key=settings.s3_faiss_key,
            documents_key=f"{settings.s3_data_prefix}documents.json",
        )
        _faiss_index = retriever.index
        _documents_cache = retriever.documents
        return retriever
    except Exception as e:
        logger.warning(f"Could not load index from S3: {e}")

    raise ValueError("Could not load FAISS index from local files or S3")


def retriever_node(state: GraphState) -> GraphState:
    """
    LangGraph node that retrieves relevant documents.

    Args:
        state: Current graph state

    Returns:
        Updated state with documents
    """
    query = state['query']
    vehicle_info = state.get('vehicle_info')
    query_type = state.get('query_type', 'symptom')

    logger.info(f"Retrieving documents for: {query[:100]}...")
    logger.info(f"Vehicle filter: {vehicle_info}")
    logger.info(f"Query type: {query_type}")

    try:
        retriever = get_retriever()

        # Determine document types to search
        filter_types = None
        if query_type == 'recall':
            filter_types = ['recall']
        elif query_type == 'complaint':
            filter_types = ['complaint']
        # For symptom/general, search all types

        # Build vehicle filter
        filter_vehicle = None
        if vehicle_info:
            filter_vehicle = {
                k: v for k, v in vehicle_info.items()
                if v is not None
            }

        # Perform search
        results = retriever.search(
            query=query,
            k=settings.max_documents_to_retrieve,
            filter_types=filter_types,
            filter_vehicle=filter_vehicle if filter_vehicle else None,
        )

        # Convert to Document format
        documents = []
        for doc, score in results:
            documents.append(Document(
                id=doc.get('id', ''),
                type=doc.get('type', 'recall'),
                campaign_number=doc.get('campaign_number'),
                odi_number=doc.get('odi_number'),
                subject=doc.get('subject'),
                component=doc.get('component'),
                summary=doc.get('summary', ''),
                consequence=doc.get('consequence'),
                remedy=doc.get('remedy'),
                vehicle=doc.get('vehicle', {}),
                relevance_score=score,
            ))

        state['documents'] = documents
        logger.info(f"Retrieved {len(documents)} documents")

        # If no results with vehicle filter, try without
        if not documents and filter_vehicle:
            logger.info("No results with vehicle filter, trying without...")
            results = retriever.search(
                query=query,
                k=settings.max_documents_to_retrieve,
                filter_types=filter_types,
            )
            documents = []
            for doc, score in results:
                documents.append(Document(
                    id=doc.get('id', ''),
                    type=doc.get('type', 'recall'),
                    campaign_number=doc.get('campaign_number'),
                    odi_number=doc.get('odi_number'),
                    subject=doc.get('subject'),
                    component=doc.get('component'),
                    summary=doc.get('summary', ''),
                    consequence=doc.get('consequence'),
                    remedy=doc.get('remedy'),
                    vehicle=doc.get('vehicle', {}),
                    relevance_score=score,
                ))
            state['documents'] = documents
            logger.info(f"Retrieved {len(documents)} documents without vehicle filter")

    except Exception as e:
        logger.error(f"Error retrieving documents: {e}")
        state['error'] = f"Failed to retrieve documents: {str(e)}"
        state['documents'] = []

    return state
