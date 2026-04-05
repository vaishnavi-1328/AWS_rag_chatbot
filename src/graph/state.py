"""
LangGraph state schema for NHTSA Recall Analyzer.

Defines the TypedDict that flows through the graph nodes.
"""

from typing import Annotated, Any, Literal, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class VehicleInfo(TypedDict):
    """Extracted vehicle information."""
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    engine: Optional[str]  # e.g., "3.5L EcoBoost"


class Document(TypedDict):
    """Retrieved document from NHTSA data."""
    id: str
    type: Literal["recall", "complaint"]
    campaign_number: Optional[str]  # For recalls
    odi_number: Optional[str]  # For complaints
    subject: Optional[str]
    component: Optional[str]
    summary: str
    consequence: Optional[str]
    remedy: Optional[str]
    vehicle: VehicleInfo
    relevance_score: float  # Set by grader


class GraphState(TypedDict):
    """
    The state that flows through the LangGraph.

    Attributes:
        query: Original user query
        vehicle_info: Extracted vehicle information
        query_type: Classified query type (recall/tsb/complaint/general)
        documents: Retrieved documents from FAISS
        graded_documents: Documents after relevance grading
        response: Generated response
        sources: Source citations
        error: Error message if any
        iteration: Current iteration count (for retry logic)
    """
    # Input
    query: str

    # Extracted info
    vehicle_info: Optional[VehicleInfo]
    query_type: Optional[Literal["recall", "tsb", "complaint", "symptom", "general"]]

    # Retrieved data
    documents: list[Document]
    graded_documents: list[Document]

    # Output
    response: Optional[str]
    sources: list[dict]

    # Control flow
    error: Optional[str]
    iteration: int
    needs_clarification: bool
    clarification_question: Optional[str]


def create_initial_state(query: str) -> GraphState:
    """Create initial state from user query."""
    return GraphState(
        query=query,
        vehicle_info=None,
        query_type=None,
        documents=[],
        graded_documents=[],
        response=None,
        sources=[],
        error=None,
        iteration=0,
        needs_clarification=False,
        clarification_question=None,
    )
