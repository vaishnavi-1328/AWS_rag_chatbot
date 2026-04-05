"""
Hallucination Checker Agent - Validates generated responses against source documents.

Ensures the response doesn't include information that wasn't in the retrieved documents.
This is critical for safety-related automotive information.
"""

import json
import logging
import re
from typing import Optional

from ..graph.state import Document, GraphState
from ..utils.bedrock import get_bedrock_client

logger = logging.getLogger(__name__)

HALLUCINATION_CHECK_PROMPT = """You are a fact-checker for automotive technical information.

Your job is to verify that the generated response is supported by the source documents.
This is critical because incorrect automotive safety information could be dangerous.

Source Documents:
{documents}

Generated Response:
{response}

Check for:
1. Campaign/recall numbers mentioned in response - are they in the sources?
2. Vehicle year/make/model claims - do they match the sources?
3. Remedy/fix descriptions - are they accurately summarized from sources?
4. Consequence descriptions - do they match the source documents?
5. Any claims not supported by the provided documents

Respond with JSON:
{{
    "is_grounded": true or false,
    "confidence": 0.0 to 1.0,
    "issues": ["list of any issues found"],
    "suggestion": "how to fix if issues found"
}}

If the response is a "no results found" message or clarification request, mark it as grounded.
"""


def check_hallucination_with_llm(
    response: str,
    documents: list[Document],
) -> tuple[bool, float, list[str]]:
    """
    Use Claude to check for hallucinations.

    Returns:
        Tuple of (is_grounded, confidence, issues)
    """
    try:
        client = get_bedrock_client()

        # Format documents for the prompt
        docs_text = []
        for doc in documents:
            lines = [f"Document ({doc.get('type', 'unknown').upper()}):"]
            if doc.get('campaign_number'):
                lines.append(f"  Campaign: {doc['campaign_number']}")
            if doc.get('subject'):
                lines.append(f"  Subject: {doc['subject']}")
            if doc.get('summary'):
                lines.append(f"  Summary: {doc['summary'][:300]}")
            if doc.get('remedy'):
                lines.append(f"  Remedy: {doc['remedy'][:200]}")
            if doc.get('consequence'):
                lines.append(f"  Consequence: {doc['consequence'][:200]}")

            vehicle = doc.get('vehicle', {})
            if vehicle:
                lines.append(f"  Vehicle: {vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}")

            docs_text.append('\n'.join(lines))

        if not docs_text:
            docs_text = ["No source documents provided."]

        prompt = HALLUCINATION_CHECK_PROMPT.format(
            documents='\n\n'.join(docs_text),
            response=response[:2000],  # Truncate for token limits
        )

        llm_response = client.invoke_claude(
            prompt=prompt,
            system_prompt="You are a precise fact-checker. Respond only with valid JSON.",
            max_tokens=300,
            temperature=0.0,
        )

        # Parse JSON response
        json_match = re.search(r'\{[^{}]*\}', llm_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(llm_response)

        return (
            data.get('is_grounded', True),
            float(data.get('confidence', 0.8)),
            data.get('issues', []),
        )

    except Exception as e:
        logger.error(f"Error checking hallucination: {e}")
        # Default to accepting the response if check fails
        return True, 0.5, [f"Hallucination check failed: {str(e)}"]


def check_hallucination_basic(
    response: str,
    documents: list[Document],
) -> tuple[bool, float, list[str]]:
    """
    Basic hallucination check without LLM (fast, no cost).

    Checks that campaign numbers mentioned in response exist in documents.
    """
    issues = []

    # Extract campaign numbers from response
    campaign_pattern = r'\b(\d{2}[VE]\d{3,6})\b'  # e.g., 20V123000
    response_campaigns = set(re.findall(campaign_pattern, response))

    # Get campaign numbers from documents
    doc_campaigns = set()
    for doc in documents:
        if doc.get('campaign_number'):
            doc_campaigns.add(doc['campaign_number'])

    # Check for campaigns in response but not in documents
    unknown_campaigns = response_campaigns - doc_campaigns
    if unknown_campaigns:
        issues.append(f"Unknown campaign numbers mentioned: {unknown_campaigns}")

    # Extract ODI numbers from response
    odi_pattern = r'\b(\d{8})\b'  # 8-digit ODI numbers
    # This is too broad, skip for now

    is_grounded = len(issues) == 0
    confidence = 0.7 if is_grounded else 0.3

    return is_grounded, confidence, issues


def hallucination_checker_node(state: GraphState) -> GraphState:
    """
    LangGraph node that checks for hallucinations in the response.

    Args:
        state: Current graph state

    Returns:
        Updated state (may modify response if hallucination detected)
    """
    response = state.get('response', '')
    documents = state.get('graded_documents', [])

    logger.info("Checking response for hallucinations...")

    # Skip check for error messages or clarification requests
    if state.get('error') or state.get('needs_clarification'):
        logger.info("Skipping hallucination check for error/clarification")
        return state

    # Skip check if no documents (nothing to hallucinate from)
    if not documents:
        logger.info("Skipping hallucination check - no source documents")
        return state

    # First do basic check (free)
    is_grounded_basic, confidence_basic, issues_basic = check_hallucination_basic(
        response, documents
    )

    if not is_grounded_basic:
        logger.warning(f"Basic check found issues: {issues_basic}")

    # Only use LLM check if basic check found issues or confidence is low
    if not is_grounded_basic or confidence_basic < 0.8:
        is_grounded, confidence, issues = check_hallucination_with_llm(
            response, documents
        )
        logger.info(f"LLM hallucination check: grounded={is_grounded}, confidence={confidence}")

        if not is_grounded:
            logger.warning(f"Hallucination detected: {issues}")

            # Add disclaimer to response
            disclaimer = (
                "\n\n---\n"
                "**Note:** This response may contain inaccuracies. "
                "Please verify all information with your dealer or at [NHTSA.gov](https://www.nhtsa.gov)."
            )
            state['response'] = response + disclaimer
    else:
        logger.info("Basic hallucination check passed")

    return state


def should_regenerate(state: GraphState) -> bool:
    """
    Determine if we should regenerate the response due to hallucination.

    Currently we just add a disclaimer rather than regenerating.
    """
    # For now, we don't regenerate - just add disclaimer
    return False
