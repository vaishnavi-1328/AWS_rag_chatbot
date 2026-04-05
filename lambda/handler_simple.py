"""
Simplified Lambda Handler for NHTSA Recall Analyzer
====================================================

This is a lightweight Lambda handler that uses only boto3 (pre-installed in Lambda).
It demonstrates the core RAG pattern without heavy dependencies like LangGraph or FAISS.

WHY SIMPLIFIED VERSION?
-----------------------
The full version with LangGraph + FAISS + LangChain exceeds Lambda's 250MB limit.
Options to use full version:
1. Docker container image (supports up to 10GB)
2. Lambda Layers (complex, still has 250MB total limit)
3. AWS Fargate or ECS for compute

This simplified version:
- Uses regex for vehicle parsing (no LLM call needed for 80% of queries)
- Uses keyword matching for query classification
- Uses sample data instead of FAISS vector search
- Calls Bedrock Claude only for response generation

ARCHITECTURE:
-------------
User Query → Lambda → Bedrock Claude → Response

1. Parse vehicle info from query (regex)
2. Classify query type (keyword matching)
3. Get relevant sample data
4. Generate response with Bedrock Claude
5. Return formatted JSON response

REQUIRED IAM PERMISSIONS:
-------------------------
- AWSLambdaBasicExecutionRole (CloudWatch Logs)
- AmazonBedrockFullAccess (Bedrock model invocation)
- AmazonS3ReadOnlyAccess (optional, if using S3 data)

ENVIRONMENT VARIABLES:
----------------------
- AWS_REGION: AWS region (default: us-east-1)
- S3_BUCKET_NAME: S3 bucket for data (optional)
- LOG_LEVEL: Logging level (default: INFO)
"""

import json
import boto3
import os
import re
from typing import Optional

# =============================================================================
# GLOBAL VARIABLES (persist across warm Lambda invocations)
# =============================================================================
# Why global? Lambda reuses execution environments for subsequent invocations.
# By caching the client, we avoid re-initializing on every request (faster).
bedrock_runtime = None


def get_bedrock_client():
    """
    Get or create Bedrock runtime client.

    Uses lazy initialization to reduce cold start time.
    The client persists across warm invocations.

    Returns:
        boto3.client: Bedrock runtime client
    """
    global bedrock_runtime
    if bedrock_runtime is None:
        bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
    return bedrock_runtime


# =============================================================================
# VEHICLE PARSING (Step 1 of the pipeline)
# =============================================================================
def parse_vehicle_info(query: str) -> dict:
    """
    Extract vehicle information (year, make, model) from user query.

    Uses regex pattern matching - no LLM call needed for most queries.
    This handles ~80% of queries and saves Bedrock API costs.

    Examples:
        "2019 Ford F-150 engine stalls" → {year: "2019", make: "Ford", model: "F-150"}
        "my Camry has brake problems" → {year: None, make: "Toyota", model: "Camry"}

    Why regex over LLM?
        - Free (no API call)
        - Fast (~1ms vs ~500ms)
        - Deterministic results

    Args:
        query: User's natural language query

    Returns:
        dict with keys: year, make, model (values may be None)
    """

    # Year pattern: 4 digits starting with 19 or 20
    year_pattern = r'(19|20)\d{2}'

    # Known makes (lowercase for matching)
    # Includes common variations (chevy → Chevrolet)
    makes = ['ford', 'chevrolet', 'chevy', 'toyota', 'honda', 'nissan', 'dodge',
             'ram', 'gmc', 'bmw', 'mercedes', 'audi', 'volkswagen', 'vw', 'hyundai',
             'kia', 'subaru', 'mazda', 'lexus', 'acura', 'infiniti', 'jeep']

    # Known models (lowercase for matching)
    # Popular models from major manufacturers
    models = ['f-150', 'f150', 'silverado', 'camry', 'accord', 'civic', 'altima',
              'mustang', 'corvette', 'tacoma', 'rav4', 'cr-v', 'crv', 'pilot',
              'explorer', 'escape', 'edge', 'fusion', 'focus', 'ranger', 'bronco']

    query_lower = query.lower()

    # Extract year using regex
    year_match = re.search(year_pattern, query)
    year = year_match.group(0) if year_match else None

    # Extract make (normalize variations)
    make = None
    for m in makes:
        if m in query_lower:
            make = m.title()
            # Normalize common abbreviations
            if make == 'Chevy':
                make = 'Chevrolet'
            elif make == 'Vw':
                make = 'Volkswagen'
            break

    # Extract model
    model = None
    for m in models:
        if m in query_lower:
            # Format model name (uppercase for short names, title case for others)
            model = m.upper() if '-' in m or len(m) <= 4 else m.title()
            break

    return {
        'year': year,
        'make': make,
        'model': model
    }


# =============================================================================
# QUERY CLASSIFICATION (Step 2 of the pipeline)
# =============================================================================
def classify_query(query: str) -> str:
    """
    Classify query into categories for targeted search.

    Categories:
        - recall: User asking about safety recalls
        - tsb: User asking about Technical Service Bulletins
        - complaint: User asking about consumer complaints
        - general: General vehicle question (search all)

    Why classification matters?
        Different query types need different search strategies.
        A recall query shouldn't return TSBs (reduces noise).

    Uses keyword matching - fast and deterministic.
    Full version uses LLM for ambiguous cases.

    Args:
        query: User's natural language query

    Returns:
        str: Query category
    """
    query_lower = query.lower()

    if 'recall' in query_lower:
        return 'recall'
    elif 'tsb' in query_lower or 'technical service' in query_lower:
        return 'tsb'
    elif 'complaint' in query_lower:
        return 'complaint'
    else:
        return 'general'


# =============================================================================
# DATA RETRIEVAL (Step 3 of the pipeline)
# =============================================================================
def get_sample_data(vehicle_info: dict, query_type: str) -> list:
    """
    Get sample NHTSA data for demonstration.

    In the FULL version, this would:
        1. Load FAISS index from S3
        2. Embed the query using Bedrock Titan
        3. Search for similar documents
        4. Filter by vehicle make/model/year
        5. Return top-K relevant documents

    For the SIMPLIFIED version, we return sample data that
    demonstrates the response format without actual retrieval.

    Note: The sample data is dynamically generated to match
    the user's vehicle query for a realistic demo experience.

    Args:
        vehicle_info: Dict with year, make, model
        query_type: Category from classify_query()

    Returns:
        list: Sample documents matching the query
    """

    # Use extracted vehicle info or defaults
    make = vehicle_info.get('make') or 'Ford'
    model = vehicle_info.get('model') or 'F-150'
    year = vehicle_info.get('year') or '2019'

    # Sample recall data
    sample_recalls = [
        {
            "campaign_number": "23V456",
            "make": make,
            "model": model,
            "year": year,
            "component": "FUEL SYSTEM",
            "summary": f"Certain {year} {make} {model} vehicles may experience fuel pump failure, which can cause the engine to stall without warning.",
            "remedy": "Dealers will replace the fuel pump free of charge.",
            "report_date": "2023-08-15"
        },
        {
            "campaign_number": "22V789",
            "make": make,
            "model": model,
            "year": str(int(year) - 1) if year else "2018",
            "component": "AIR BAGS",
            "summary": f"The front passenger air bag may not deploy correctly in certain crash conditions.",
            "remedy": "Dealers will update the air bag control module software.",
            "report_date": "2022-11-20"
        }
    ]

    # Sample TSB data
    sample_tsbs = [
        {
            "tsb_number": "TSB-21-2345",
            "make": make,
            "model": model,
            "year": year,
            "component": "ENGINE",
            "summary": f"Some {year} {make} {model} owners may experience rough idle or engine hesitation at low speeds.",
            "remedy": "Reprogram the powertrain control module (PCM) to the latest calibration."
        }
    ]

    # Sample complaint data
    sample_complaints = [
        {
            "odi_number": "11234567",
            "make": make,
            "model": model,
            "year": year,
            "component": "ELECTRICAL SYSTEM",
            "summary": "Battery drains overnight even when vehicle is off. Multiple owners reporting same issue.",
            "crash": False,
            "fire": False
        }
    ]

    # Return appropriate data based on query type
    if query_type == 'recall':
        return sample_recalls
    elif query_type == 'tsb':
        return sample_tsbs
    elif query_type == 'complaint':
        return sample_complaints
    else:
        # General query - return mix of data
        return sample_recalls + sample_tsbs


# =============================================================================
# RESPONSE GENERATION (Step 4 of the pipeline)
# =============================================================================
def generate_response_with_bedrock(query: str, vehicle_info: dict, documents: list) -> str:
    """
    Generate natural language response using Claude via Bedrock.

    This is the core RAG (Retrieval Augmented Generation) step:
    - Context (documents) provides factual grounding
    - LLM (Claude) synthesizes a coherent response

    The prompt engineering ensures:
    1. Direct answer to user's question
    2. Campaign numbers for verification
    3. Clear remedy/next steps
    4. Disclaimer for safety-critical info

    Model: Claude 3 Haiku
    Why Haiku? 12x cheaper than Sonnet, sufficient for summarization.

    Args:
        query: User's original question
        vehicle_info: Extracted vehicle details
        documents: Retrieved/sample documents

    Returns:
        str: AI-generated response
    """

    client = get_bedrock_client()

    # Format documents as context for the LLM
    docs_text = "\n\n".join([
        f"Document {i+1}:\n" + "\n".join([f"- {k}: {v}" for k, v in doc.items()])
        for i, doc in enumerate(documents)
    ])

    # Build vehicle string for prompt
    vehicle_str = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}".strip()

    # Prompt engineering for structured, accurate responses
    prompt = f"""Based on the following NHTSA documents, answer the user's question about {vehicle_str if vehicle_str else 'their vehicle'}.

User Question: {query}

Relevant Documents:
{docs_text}

Provide a helpful, concise response that:
1. Directly answers the question
2. Lists any relevant recall campaign numbers
3. Explains what the issue is and the remedy
4. Recommends contacting a dealer or checking NHTSA.gov for official information

Response:"""

    try:
        # Call Bedrock Claude API
        # API format specific to Anthropic Claude models
        response = client.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",  # Required version string
                "max_tokens": 1024,  # Limit response length
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
        )

        # Parse response
        result = json.loads(response['body'].read())
        return result['content'][0]['text']

    except Exception as e:
        # Fallback if Bedrock fails (rate limit, network, etc.)
        print(f"Bedrock error: {str(e)}")
        return generate_fallback_response(vehicle_info, documents)


def generate_fallback_response(vehicle_info: dict, documents: list) -> str:
    """
    Generate response without LLM if Bedrock fails.

    This provides a basic, templated response using the
    document data directly. Less natural but still useful.

    Triggers when:
    - Bedrock rate limited
    - Network issues
    - Invalid credentials

    Args:
        vehicle_info: Extracted vehicle details
        documents: Retrieved/sample documents

    Returns:
        str: Template-based response
    """

    vehicle_str = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}".strip()

    response = f"Here's what I found for {vehicle_str}:\n\n"

    for doc in documents:
        if 'campaign_number' in doc:
            response += f"**Recall {doc['campaign_number']}**\n"
            response += f"- Component: {doc.get('component', 'N/A')}\n"
            response += f"- Issue: {doc.get('summary', 'N/A')}\n"
            response += f"- Remedy: {doc.get('remedy', 'N/A')}\n\n"
        elif 'tsb_number' in doc:
            response += f"**TSB {doc['tsb_number']}**\n"
            response += f"- Component: {doc.get('component', 'N/A')}\n"
            response += f"- Issue: {doc.get('summary', 'N/A')}\n\n"

    response += "\n*Please verify this information at NHTSA.gov or contact your dealer.*"
    return response


# =============================================================================
# LAMBDA HANDLER (Entry Point)
# =============================================================================
def lambda_handler(event, context):
    """
    Main Lambda entry point.

    Handles requests from API Gateway with Lambda Proxy Integration.

    Request format (from API Gateway):
    {
        "body": "{\"query\": \"2019 Ford F-150 recalls\"}",
        "httpMethod": "POST",
        "headers": {...},
        "path": "/query"
    }

    Response format (to API Gateway):
    {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json", ...},
        "body": "{\"response\": \"...\", \"sources\": [...]}"
    }

    CORS headers are required because:
    - Frontend runs on EC2 (different domain)
    - Browser blocks cross-origin requests by default

    Args:
        event: Request from API Gateway
        context: Lambda context (runtime info)

    Returns:
        dict: Response for API Gateway
    """

    # Log incoming event for debugging
    # View in CloudWatch Logs: Lambda → Monitor → View CloudWatch logs
    print(f"Received event: {json.dumps(event)}")

    # CORS headers - required for browser requests from different domain
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',  # Allow any origin (restrict in production)
        'Access-Control-Allow-Headers': 'Content-Type,X-Api-Key',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }

    # Handle CORS preflight request
    # Browsers send OPTIONS before POST to check if request is allowed
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }

    try:
        # =====================================================================
        # PARSE REQUEST BODY
        # =====================================================================
        # API Gateway sends body as string, need to parse JSON
        body = event.get('body', '{}')

        # Handle string body (from API Gateway)
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = {}

        # Handle None body
        if not body:
            body = {}

        # Also check if query is directly in event (for Lambda console testing)
        if 'query' in event and 'query' not in body:
            body['query'] = event['query']

        query = body.get('query', '')

        # Validate query
        if not query:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Missing query parameter'})
            }

        # =====================================================================
        # PIPELINE EXECUTION
        # =====================================================================

        # Step 1: Parse vehicle info from query
        vehicle_info = parse_vehicle_info(query)
        print(f"Parsed vehicle: {vehicle_info}")

        # Step 2: Classify query type
        query_type = classify_query(query)
        print(f"Query type: {query_type}")

        # Step 3: Get relevant documents (sample data for demo)
        documents = get_sample_data(vehicle_info, query_type)
        print(f"Retrieved {len(documents)} documents")

        # Step 4: Generate response with Bedrock Claude
        response_text = generate_response_with_bedrock(query, vehicle_info, documents)

        # =====================================================================
        # BUILD RESPONSE
        # =====================================================================
        result = {
            'response': response_text,
            'vehicle_info': vehicle_info,
            'query_type': query_type,
            'sources': [
                {
                    'id': doc.get('campaign_number') or doc.get('tsb_number') or doc.get('odi_number'),
                    'type': 'recall' if 'campaign_number' in doc else 'tsb' if 'tsb_number' in doc else 'complaint'
                }
                for doc in documents
            ]
        }

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(result)
        }

    except Exception as e:
        # Log full error for debugging
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }
