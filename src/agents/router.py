"""
Router Agent - Classifies user queries into search categories.

Determines whether the user is looking for:
- Recalls (safety issues, manufacturer campaigns)
- TSBs (technical service bulletins)
- Complaints (consumer-reported issues)
- Symptoms (general troubleshooting)
"""

import json
import logging
import re
from typing import Literal

from ..graph.state import GraphState
from ..utils.bedrock import get_bedrock_client

logger = logging.getLogger(__name__)

QueryType = Literal["recall", "tsb", "complaint", "symptom", "general"]

ROUTER_PROMPT = """You are a query classifier for an automotive technical database.

Classify the user's query into one of these categories:
- "recall": User is asking about safety recalls, manufacturer recalls, campaign numbers
- "tsb": User is asking about Technical Service Bulletins, service updates, known fixes
- "complaint": User wants to see consumer complaints, reported issues, common problems
- "symptom": User describes a symptom/problem and wants to find related issues
- "general": General question about a vehicle or catch-all

Classification rules:
1. If query mentions "recall", "campaign", or asks if there are recalls -> "recall"
2. If query mentions "TSB", "bulletin", "service bulletin" -> "tsb"
3. If query mentions "complaints", "reported issues", "common problems" -> "complaint"
4. If query describes a symptom without specifying type (e.g., "my car stalls") -> "symptom"
5. If query is about comparing vehicles, general info -> "general"

For "symptom" queries, we'll search ALL document types to find matches.

Respond with ONLY the category name, nothing else.

Query: {query}
"""


def classify_query_with_keywords(query: str) -> tuple[QueryType, float]:
    """
    Quick keyword-based classification.
    Returns (query_type, confidence).
    """
    query_lower = query.lower()

    # Recall keywords
    recall_keywords = ['recall', 'recalled', 'campaign', 'safety recall', 'nhtsa recall']
    if any(kw in query_lower for kw in recall_keywords):
        return 'recall', 0.9

    # TSB keywords
    tsb_keywords = ['tsb', 'bulletin', 'service bulletin', 'technical bulletin', 'known fix']
    if any(kw in query_lower for kw in tsb_keywords):
        return 'tsb', 0.9

    # Complaint keywords
    complaint_keywords = ['complaint', 'complaints', 'reported', 'common problem', 'issues reported']
    if any(kw in query_lower for kw in complaint_keywords):
        return 'complaint', 0.9

    # Symptom patterns (describes a problem)
    symptom_patterns = [
        r'\b(stall|stalls|stalling)\b',
        r'\b(shudder|shudders|shuddering)\b',
        r'\b(noise|noisy|sound)\b',
        r'\b(leak|leaking|leaks)\b',
        r'\b(won\'?t start|doesn\'?t start)\b',
        r'\b(check engine|engine light)\b',
        r'\b(hesitation|hesitates)\b',
        r'\b(vibration|vibrates)\b',
        r'\b(rough idle)\b',
        r'\b(overheating|overheats)\b',
    ]
    for pattern in symptom_patterns:
        if re.search(pattern, query_lower):
            return 'symptom', 0.7

    # Default to general with low confidence
    return 'general', 0.3


def classify_query_with_llm(query: str) -> QueryType:
    """Use Claude to classify the query."""
    try:
        client = get_bedrock_client()
        prompt = ROUTER_PROMPT.format(query=query)

        response = client.invoke_claude(
            prompt=prompt,
            system_prompt="You are a precise classifier. Respond with only one word from: recall, tsb, complaint, symptom, general",
            max_tokens=20,
            temperature=0.0,
        )

        # Clean response
        response = response.strip().lower()

        # Map to valid type
        valid_types = ['recall', 'tsb', 'complaint', 'symptom', 'general']
        if response in valid_types:
            return response

        # Try to find valid type in response
        for vt in valid_types:
            if vt in response:
                return vt

        return 'symptom'  # Default fallback

    except Exception as e:
        logger.error(f"Error classifying with LLM: {e}")
        return 'symptom'


def router_node(state: GraphState) -> GraphState:
    """
    LangGraph node that classifies the query type.

    Args:
        state: Current graph state

    Returns:
        Updated state with query_type
    """
    query = state['query']
    logger.info(f"Routing query: {query[:100]}...")

    # First try keyword classification
    keyword_type, confidence = classify_query_with_keywords(query)

    if confidence >= 0.8:
        # High confidence from keywords, use it
        logger.info(f"Keyword classification: {keyword_type} (confidence: {confidence})")
        state['query_type'] = keyword_type
        return state

    # Use LLM for better classification
    llm_type = classify_query_with_llm(query)
    logger.info(f"LLM classification: {llm_type}")

    # If keyword had medium confidence and matches LLM, use it
    if confidence >= 0.5 and keyword_type == llm_type:
        state['query_type'] = keyword_type
    else:
        state['query_type'] = llm_type

    return state


def should_search_all_types(state: GraphState) -> bool:
    """
    Determine if we should search all document types.

    For symptom queries, we search everything to find relevant matches.
    """
    return state.get('query_type') == 'symptom'


def get_search_types(state: GraphState) -> list[str]:
    """
    Get the document types to search based on query classification.
    """
    query_type = state.get('query_type', 'symptom')

    if query_type == 'symptom' or query_type == 'general':
        # Search everything
        return ['recall', 'complaint']
    elif query_type == 'recall':
        return ['recall']
    elif query_type == 'tsb':
        # TSBs are often mixed with recalls in NHTSA data
        return ['recall']
    elif query_type == 'complaint':
        return ['complaint']
    else:
        return ['recall', 'complaint']
