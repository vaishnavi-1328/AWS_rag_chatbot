"""
Grader Agent - Scores document relevance to the user query.

Uses Claude to evaluate whether retrieved documents actually
answer the user's question or match their symptoms.
"""

import json
import logging
import re
from typing import Optional

from ..graph.state import Document, GraphState
from ..utils.bedrock import get_bedrock_client
from ..utils.config import settings

logger = logging.getLogger(__name__)

GRADER_PROMPT = """You are a relevance grader for automotive technical documents.

Given a user's query about a vehicle issue and a retrieved document, determine if the document is relevant.

User Query: {query}
Vehicle: {vehicle}

Document:
Type: {doc_type}
{doc_id}
Component: {component}
Summary: {summary}
{extra_info}

Is this document relevant to answering the user's query?

Consider:
1. Does the document address the same symptom/issue?
2. Is the document for the same or similar vehicle?
3. Does the document provide useful information for the user's problem?

Respond with a JSON object:
{{
    "relevant": true or false,
    "score": 0.0 to 1.0,
    "reason": "brief explanation"
}}
"""


def grade_document_with_llm(
    query: str,
    vehicle_info: dict,
    document: Document,
) -> tuple[bool, float, str]:
    """
    Use Claude to grade document relevance.

    Returns:
        Tuple of (is_relevant, score, reason)
    """
    try:
        client = get_bedrock_client()

        # Build vehicle string
        vehicle_str = "Not specified"
        if vehicle_info:
            parts = []
            if vehicle_info.get('year'):
                parts.append(str(vehicle_info['year']))
            if vehicle_info.get('make'):
                parts.append(vehicle_info['make'])
            if vehicle_info.get('model'):
                parts.append(vehicle_info['model'])
            if parts:
                vehicle_str = ' '.join(parts)

        # Build document ID string
        doc_id = ""
        if document.get('campaign_number'):
            doc_id = f"Campaign: {document['campaign_number']}"
        elif document.get('odi_number'):
            doc_id = f"ODI Number: {document['odi_number']}"

        # Build extra info
        extra_parts = []
        if document.get('consequence'):
            extra_parts.append(f"Consequence: {document['consequence']}")
        if document.get('remedy'):
            extra_parts.append(f"Remedy: {document['remedy']}")
        extra_info = '\n'.join(extra_parts)

        prompt = GRADER_PROMPT.format(
            query=query,
            vehicle=vehicle_str,
            doc_type=document.get('type', 'unknown').upper(),
            doc_id=doc_id,
            component=document.get('component', 'Unknown'),
            summary=document.get('summary', '')[:500],  # Truncate for token limits
            extra_info=extra_info,
        )

        response = client.invoke_claude(
            prompt=prompt,
            system_prompt="You are a precise relevance grader. Respond only with valid JSON.",
            max_tokens=200,
            temperature=0.0,
        )

        # Parse JSON response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response)

        return (
            data.get('relevant', False),
            float(data.get('score', 0.0)),
            data.get('reason', ''),
        )

    except Exception as e:
        logger.error(f"Error grading document with LLM: {e}")
        # Fall back to basic scoring
        return True, document.get('relevance_score', 0.5), "LLM grading failed, using retrieval score"


def grade_document_basic(
    query: str,
    vehicle_info: dict,
    document: Document,
) -> tuple[bool, float, str]:
    """
    Basic keyword-based document grading (no LLM cost).
    """
    score = document.get('relevance_score', 0.5)
    query_lower = query.lower()
    summary_lower = (document.get('summary', '') or '').lower()

    # Boost score if key terms match
    query_terms = set(query_lower.split())
    summary_terms = set(summary_lower.split())

    # Remove common words
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'and', 'or', 'my', 'i', 'to', 'for', 'in', 'on'}
    query_terms = query_terms - stop_words
    summary_terms = summary_terms - stop_words

    # Calculate overlap
    overlap = len(query_terms & summary_terms)
    if overlap >= 3:
        score = min(score + 0.2, 1.0)
    elif overlap >= 1:
        score = min(score + 0.1, 1.0)

    # Check vehicle match
    if vehicle_info:
        doc_vehicle = document.get('vehicle', {})

        # Make match bonus
        if vehicle_info.get('make') and doc_vehicle.get('make'):
            if vehicle_info['make'].lower() == doc_vehicle['make'].lower():
                score = min(score + 0.15, 1.0)

        # Model match bonus
        if vehicle_info.get('model') and doc_vehicle.get('model'):
            if vehicle_info['model'].lower() in doc_vehicle['model'].lower():
                score = min(score + 0.15, 1.0)

        # Year match bonus
        if vehicle_info.get('year') and doc_vehicle.get('year'):
            year_diff = abs(vehicle_info['year'] - doc_vehicle['year'])
            if year_diff == 0:
                score = min(score + 0.1, 1.0)
            elif year_diff <= 2:
                score = min(score + 0.05, 1.0)

    is_relevant = score >= settings.relevance_threshold
    reason = f"Basic scoring: {overlap} term matches"

    return is_relevant, score, reason


def grader_node(state: GraphState) -> GraphState:
    """
    LangGraph node that grades document relevance.

    Args:
        state: Current graph state

    Returns:
        Updated state with graded_documents
    """
    query = state['query']
    vehicle_info = state.get('vehicle_info', {})
    documents = state.get('documents', [])

    logger.info(f"Grading {len(documents)} documents...")

    graded_documents = []
    use_llm_grading = len(documents) <= 5  # Only use LLM for small sets (cost optimization)

    for doc in documents:
        if use_llm_grading:
            is_relevant, score, reason = grade_document_with_llm(
                query, vehicle_info, doc
            )
        else:
            is_relevant, score, reason = grade_document_basic(
                query, vehicle_info, doc
            )

        # Update document with graded score
        graded_doc = dict(doc)
        graded_doc['relevance_score'] = score

        if is_relevant:
            graded_documents.append(graded_doc)
            logger.debug(f"Relevant: {doc.get('id')} (score: {score:.2f}) - {reason}")
        else:
            logger.debug(f"Not relevant: {doc.get('id')} (score: {score:.2f}) - {reason}")

    # Sort by relevance score
    graded_documents.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

    # Keep top results
    graded_documents = graded_documents[:5]

    state['graded_documents'] = graded_documents
    logger.info(f"After grading: {len(graded_documents)} relevant documents")

    return state


def has_relevant_documents(state: GraphState) -> bool:
    """Check if we have any relevant documents after grading."""
    return len(state.get('graded_documents', [])) > 0
