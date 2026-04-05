"""
Main LangGraph workflow for NHTSA Recall Analyzer.

Orchestrates the flow:
Vehicle Parser → Router → Retriever → Grader → Generator → Hallucination Checker
"""

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from .state import GraphState, create_initial_state
from ..agents.vehicle_parser import vehicle_parser_node
from ..agents.router import router_node
from ..agents.retriever import retriever_node
from ..agents.grader import grader_node, has_relevant_documents
from ..agents.generator import generator_node
from ..agents.hallucination import hallucination_checker_node

logger = logging.getLogger(__name__)


def should_continue_after_vehicle_parse(state: GraphState) -> Literal["router", "clarify"]:
    """Determine next step after vehicle parsing."""
    if state.get('needs_clarification'):
        return "clarify"
    return "router"


def should_continue_after_grading(state: GraphState) -> Literal["generate", "fallback"]:
    """Determine next step after grading documents."""
    if has_relevant_documents(state):
        return "generate"
    return "fallback"


def clarification_node(state: GraphState) -> GraphState:
    """Handle clarification requests."""
    # The clarification question is already set by vehicle_parser
    state['response'] = state.get('clarification_question', 'Could you provide more details about your vehicle?')
    return state


def fallback_node(state: GraphState) -> GraphState:
    """Handle case when no relevant documents found."""
    vehicle_info = state.get('vehicle_info', {})
    query = state['query']

    vehicle_str = "your vehicle"
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

    state['response'] = f"""## No Matching Documents Found

I searched our database but couldn't find recalls or complaints that closely match your query about {vehicle_str}.

### What I Searched For:
- **Vehicle:** {vehicle_str}
- **Issue:** {query}

### Suggested Next Steps:

1. **Search NHTSA directly:**
   Visit [NHTSA Vehicle Search](https://www.nhtsa.gov/vehicle) and enter your VIN for the most accurate results.

2. **Contact your dealer:**
   They can check for open recalls and TSBs using your VIN.

3. **Try a different search:**
   - Be more specific about symptoms (e.g., "engine stalls at idle")
   - Or try "all recalls for {vehicle_str}"

### File a Complaint:
If you're experiencing a safety issue, you can [file a complaint with NHTSA](https://www.nhtsa.gov/report-a-safety-problem).
"""

    state['sources'] = []
    return state


def build_graph() -> StateGraph:
    """Build and compile the LangGraph workflow."""

    # Create the graph
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("vehicle_parser", vehicle_parser_node)
    workflow.add_node("router", router_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("generator", generator_node)
    workflow.add_node("hallucination_checker", hallucination_checker_node)
    workflow.add_node("clarify", clarification_node)
    workflow.add_node("fallback", fallback_node)

    # Set entry point
    workflow.set_entry_point("vehicle_parser")

    # Add conditional edges
    workflow.add_conditional_edges(
        "vehicle_parser",
        should_continue_after_vehicle_parse,
        {
            "router": "router",
            "clarify": "clarify",
        }
    )

    # Router always goes to retriever
    workflow.add_edge("router", "retriever")

    # Retriever goes to grader
    workflow.add_edge("retriever", "grader")

    # Grader conditionally goes to generator or fallback
    workflow.add_conditional_edges(
        "grader",
        should_continue_after_grading,
        {
            "generate": "generator",
            "fallback": "fallback",
        }
    )

    # Generator goes to hallucination checker
    workflow.add_edge("generator", "hallucination_checker")

    # Terminal nodes
    workflow.add_edge("hallucination_checker", END)
    workflow.add_edge("clarify", END)
    workflow.add_edge("fallback", END)

    return workflow


# Compile the graph
_compiled_graph = None


def get_graph():
    """Get or create the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_graph()
        _compiled_graph = workflow.compile()
    return _compiled_graph


def run_query(query: str) -> dict:
    """
    Run a query through the workflow.

    Args:
        query: User's natural language query

    Returns:
        Dictionary with response and sources
    """
    logger.info(f"Processing query: {query[:100]}...")

    # Create initial state
    initial_state = create_initial_state(query)

    # Get compiled graph
    graph = get_graph()

    # Run the graph
    final_state = graph.invoke(initial_state)

    # Extract results
    result = {
        'query': query,
        'response': final_state.get('response', 'No response generated'),
        'sources': final_state.get('sources', []),
        'vehicle_info': final_state.get('vehicle_info'),
        'query_type': final_state.get('query_type'),
        'documents_found': len(final_state.get('graded_documents', [])),
        'error': final_state.get('error'),
    }

    logger.info(f"Query complete. Found {result['documents_found']} relevant documents.")

    return result


# Simple test function
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Test query
    test_query = sys.argv[1] if len(sys.argv) > 1 else "2019 Ford F-150 engine stalls"

    print(f"\nTesting query: {test_query}\n")
    print("=" * 60)

    result = run_query(test_query)

    print(f"\nVehicle Info: {result['vehicle_info']}")
    print(f"Query Type: {result['query_type']}")
    print(f"Documents Found: {result['documents_found']}")
    print(f"\nResponse:\n{result['response']}")

    if result['sources']:
        print(f"\nSources:")
        for src in result['sources']:
            print(f"  - {src['type']}: {src['id']}")
