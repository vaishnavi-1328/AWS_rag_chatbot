"""
Streamlit frontend for NHTSA Recall Analyzer.

Provides a chat interface for querying vehicle recalls and complaints.
"""

import json
import os
import requests
import streamlit as st
from typing import Optional

# Configuration
API_URL = os.environ.get('API_GATEWAY_URL', 'http://localhost:8000')
APP_TITLE = "NHTSA Recall & TSB Analyzer"
APP_DESCRIPTION = """
Find safety recalls, technical service bulletins (TSBs), and consumer complaints
for your vehicle. Just describe your issue or enter your vehicle information.
"""

# Page configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize session state variables."""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'query_count' not in st.session_state:
        st.session_state.query_count = 0


def call_api(query: str) -> dict:
    """Call the Lambda API endpoint."""
    try:
        # For local development, try to import and run directly
        if API_URL == 'http://localhost:8000' or not API_URL.startswith('http'):
            try:
                import sys
                sys.path.insert(0, '..')
                from src.graph.workflow import run_query
                return run_query(query)
            except ImportError:
                st.warning("Local mode: Could not import workflow. Using mock response.")
                return {
                    'response': f"[Mock Response]\n\nSearched for: {query}\n\nThis is a placeholder response. Configure API_GATEWAY_URL for real results.",
                    'sources': [],
                    'documents_found': 0,
                }

        # Call remote API
        response = requests.post(
            f"{API_URL}/query",
            json={'query': query},
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        return {
            'error': 'Request timed out. The query may be too complex. Please try a simpler query.',
            'response': None,
        }
    except requests.exceptions.RequestException as e:
        return {
            'error': f'API request failed: {str(e)}',
            'response': None,
        }
    except Exception as e:
        return {
            'error': f'Unexpected error: {str(e)}',
            'response': None,
        }


def display_sidebar():
    """Display sidebar with app info and example queries."""
    with st.sidebar:
        st.title("🚗 " + APP_TITLE)
        st.markdown(APP_DESCRIPTION)

        st.divider()

        st.subheader("📝 Example Queries")
        example_queries = [
            "2019 Ford F-150 engine stalls at low speed",
            "Any recalls for 2020 Toyota Camry?",
            "2018 Honda CR-V oil dilution issue",
            "Chevy Silverado transmission shudder",
            "2017 Jeep Grand Cherokee brake problems",
        ]

        for query in example_queries:
            if st.button(query, key=f"example_{hash(query)}", use_container_width=True):
                st.session_state.example_query = query

        st.divider()

        st.subheader("ℹ️ About")
        st.markdown("""
        This tool searches the NHTSA database for:
        - **Safety Recalls** - Manufacturer-issued recalls
        - **Complaints** - Consumer-reported issues
        - **TSBs** - Technical Service Bulletins

        Data is sourced from [NHTSA.gov](https://www.nhtsa.gov).

        **Always verify information with your dealer or NHTSA directly.**
        """)

        st.divider()

        # Query counter
        st.caption(f"Queries this session: {st.session_state.query_count}")

        # Debug info
        if st.checkbox("Show debug info"):
            st.json({
                'api_url': API_URL,
                'messages_count': len(st.session_state.messages),
            })


def display_chat():
    """Display chat interface."""
    st.title("🔍 Vehicle Safety Search")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            if message['role'] == 'user':
                st.write(message['content'])
            else:
                st.markdown(message['content'])

                # Display sources if available
                if message.get('sources'):
                    with st.expander("📚 Sources"):
                        for source in message['sources']:
                            st.write(f"- **{source.get('type', 'Unknown').upper()}**: {source.get('id', 'N/A')} - {source.get('subject', 'No subject')[:50]}...")

    # Check for example query from sidebar
    if 'example_query' in st.session_state:
        query = st.session_state.example_query
        del st.session_state.example_query

        # Process the example query
        process_query(query)

    # Chat input
    if prompt := st.chat_input("Describe your vehicle issue (e.g., '2019 Ford F-150 engine stalls')"):
        process_query(prompt)


def process_query(query: str):
    """Process a user query."""
    # Add user message
    st.session_state.messages.append({
        'role': 'user',
        'content': query,
    })

    # Display user message
    with st.chat_message('user'):
        st.write(query)

    # Show loading state
    with st.chat_message('assistant'):
        with st.spinner('Searching NHTSA database...'):
            result = call_api(query)

    # Process result
    if result.get('error'):
        response_content = f"❌ **Error:** {result['error']}"
        sources = []
    else:
        response_content = result.get('response', 'No response received')
        sources = result.get('sources', [])

    # Add assistant message
    st.session_state.messages.append({
        'role': 'assistant',
        'content': response_content,
        'sources': sources,
    })

    # Update query count
    st.session_state.query_count += 1

    # Rerun to display the new messages
    st.rerun()


def main():
    """Main app function."""
    init_session_state()
    display_sidebar()
    display_chat()


if __name__ == "__main__":
    main()
