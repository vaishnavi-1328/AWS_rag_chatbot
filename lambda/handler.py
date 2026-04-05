"""
AWS Lambda handler for NHTSA Recall Analyzer.

Entry point for API Gateway requests.
"""

import json
import logging
import os
import sys
import traceback

# Add src to path for imports
sys.path.insert(0, '/var/task')
sys.path.insert(0, '/var/task/src')

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lazy import for faster cold starts
_workflow = None


def get_workflow():
    """Lazy load the workflow to reduce cold start time."""
    global _workflow
    if _workflow is None:
        logger.info("Loading LangGraph workflow...")
        from src.graph.workflow import run_query
        _workflow = run_query
        logger.info("Workflow loaded successfully")
    return _workflow


def create_response(status_code: int, body: dict, cors: bool = True) -> dict:
    """Create API Gateway response with optional CORS headers."""
    response = {
        'statusCode': status_code,
        'body': json.dumps(body, ensure_ascii=False),
    }

    if cors:
        response['headers'] = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Api-Key',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
        }

    return response


def handler(event: dict, context) -> dict:
    """
    Lambda handler for query processing.

    Expected input (API Gateway proxy):
    {
        "body": "{\"query\": \"2019 Ford F-150 engine stalls\"}"
    }

    Returns:
    {
        "statusCode": 200,
        "body": "{\"response\": \"...\", \"sources\": [...]}"
    }
    """
    logger.info(f"Received event: {json.dumps(event)[:500]}...")

    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return create_response(200, {'message': 'OK'})

    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        query = body.get('query', '').strip()

        if not query:
            return create_response(400, {
                'error': 'Missing required field: query',
                'usage': 'POST with JSON body: {"query": "your question about a vehicle"}'
            })

        # Validate query length
        if len(query) > 1000:
            return create_response(400, {
                'error': 'Query too long. Maximum 1000 characters.',
            })

        logger.info(f"Processing query: {query[:100]}...")

        # Run the workflow
        run_query = get_workflow()
        result = run_query(query)

        # Check for errors
        if result.get('error'):
            logger.error(f"Workflow error: {result['error']}")
            return create_response(500, {
                'error': result['error'],
                'query': query,
            })

        # Return successful response
        return create_response(200, {
            'query': query,
            'response': result.get('response', 'No response generated'),
            'sources': result.get('sources', []),
            'vehicle_info': result.get('vehicle_info'),
            'query_type': result.get('query_type'),
            'documents_found': result.get('documents_found', 0),
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return create_response(400, {
            'error': 'Invalid JSON in request body',
            'details': str(e),
        })

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        logger.error(traceback.format_exc())
        return create_response(500, {
            'error': 'Internal server error',
            'details': str(e) if os.environ.get('DEBUG') else 'See logs for details',
        })


def health_check(event: dict, context) -> dict:
    """Health check endpoint."""
    return create_response(200, {
        'status': 'healthy',
        'service': 'nhtsa-recall-analyzer',
        'version': '1.0.0',
    })


# For local testing
if __name__ == "__main__":
    # Simulate API Gateway event
    test_event = {
        'httpMethod': 'POST',
        'body': json.dumps({
            'query': '2019 Ford F-150 engine stalls at low speed'
        })
    }

    result = handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))
