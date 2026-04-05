"""
Generator Agent - Creates the final response from graded documents.

Synthesizes information from relevant recalls/complaints/TSBs
into a helpful, structured response for the user.
"""

import logging
from typing import Optional

from ..graph.state import Document, GraphState
from ..utils.bedrock import get_bedrock_client

logger = logging.getLogger(__name__)

GENERATOR_PROMPT = """You are an automotive technical assistant helping users find relevant recalls, TSBs, and complaints for their vehicles.

Based on the user's query and the retrieved documents, provide a helpful response.

User Query: {query}
Vehicle: {vehicle}

Retrieved Documents:
{documents}

Instructions:
1. Summarize the most relevant findings for the user's specific issue
2. For recalls, include: Campaign number, affected vehicles, the problem, and the fix
3. For complaints, mention: The symptoms reported, how many similar complaints exist
4. If documents don't exactly match, explain what was found and its potential relevance
5. Always recommend the user verify with their dealer or check NHTSA.gov for the latest information
6. Be concise but thorough - prioritize actionable information

Format your response with clear sections using markdown-style headers.

If no relevant documents were found, acknowledge this and suggest:
- Checking NHTSA.gov directly
- Contacting the dealer
- Describing the issue differently

Response:
"""

NO_RESULTS_RESPONSE = """## No Exact Matches Found

I couldn't find any recalls or complaints that exactly match your query for {vehicle}.

### Suggested Next Steps:

1. **Check NHTSA.gov directly**
   - Visit [NHTSA Vehicle Complaints](https://www.nhtsa.gov/vehicle) and search for your specific vehicle

2. **Contact your dealer**
   - They have access to internal TSBs and can check for open recalls by VIN

3. **Try rephrasing your query**
   - Include specific symptoms (e.g., "stalls at idle", "transmission shudder")
   - Or ask for all recalls for your vehicle

### Your Query Details:
- **Vehicle:** {vehicle}
- **Issue:** {query}

Would you like me to search for something else?
"""


def format_documents_for_prompt(documents: list[Document]) -> str:
    """Format documents for inclusion in the prompt."""
    if not documents:
        return "No documents found."

    formatted = []
    for i, doc in enumerate(documents, 1):
        vehicle = doc.get('vehicle', {})
        vehicle_str = f"{vehicle.get('year', 'Unknown')} {vehicle.get('make', '')} {vehicle.get('model', '')}"

        lines = [f"### Document {i} ({doc.get('type', 'unknown').upper()})"]

        if doc.get('campaign_number'):
            lines.append(f"**Campaign Number:** {doc['campaign_number']}")
        if doc.get('odi_number'):
            lines.append(f"**ODI Number:** {doc['odi_number']}")

        lines.append(f"**Vehicle:** {vehicle_str}")

        if doc.get('subject'):
            lines.append(f"**Subject:** {doc['subject']}")
        if doc.get('component'):
            lines.append(f"**Component:** {doc['component']}")
        if doc.get('summary'):
            lines.append(f"**Summary:** {doc['summary']}")
        if doc.get('consequence'):
            lines.append(f"**Consequence:** {doc['consequence']}")
        if doc.get('remedy'):
            lines.append(f"**Remedy:** {doc['remedy']}")

        lines.append(f"**Relevance Score:** {doc.get('relevance_score', 0):.2f}")

        formatted.append('\n'.join(lines))

    return '\n\n---\n\n'.join(formatted)


def generate_response(
    query: str,
    vehicle_info: dict,
    documents: list[Document],
) -> str:
    """Generate response using Claude."""
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
            if vehicle_info.get('engine'):
                parts.append(f"({vehicle_info['engine']})")
            if parts:
                vehicle_str = ' '.join(parts)

        # Handle no results case
        if not documents:
            return NO_RESULTS_RESPONSE.format(
                vehicle=vehicle_str,
                query=query,
            )

        # Format documents
        docs_text = format_documents_for_prompt(documents)

        prompt = GENERATOR_PROMPT.format(
            query=query,
            vehicle=vehicle_str,
            documents=docs_text,
        )

        response = client.invoke_claude(
            prompt=prompt,
            system_prompt=(
                "You are a helpful automotive technical assistant. "
                "Provide accurate, actionable information based on the documents provided. "
                "Be concise but thorough. Use markdown formatting for clarity."
            ),
            max_tokens=1500,
            temperature=0.3,
        )

        return response

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return f"I encountered an error generating the response: {str(e)}"


def generator_node(state: GraphState) -> GraphState:
    """
    LangGraph node that generates the final response.

    Args:
        state: Current graph state

    Returns:
        Updated state with response
    """
    query = state['query']
    vehicle_info = state.get('vehicle_info', {})
    documents = state.get('graded_documents', [])

    logger.info(f"Generating response from {len(documents)} documents...")

    # Check if we need clarification first
    if state.get('needs_clarification'):
        state['response'] = state.get('clarification_question', 'Could you provide more details?')
        return state

    # Generate response
    response = generate_response(query, vehicle_info, documents)

    state['response'] = response

    # Extract sources for citation
    sources = []
    for doc in documents:
        source = {
            'type': doc.get('type'),
            'id': doc.get('campaign_number') or doc.get('odi_number') or doc.get('id'),
            'subject': doc.get('subject'),
            'relevance': doc.get('relevance_score', 0),
        }
        sources.append(source)

    state['sources'] = sources

    logger.info(f"Generated response with {len(sources)} sources")

    return state
