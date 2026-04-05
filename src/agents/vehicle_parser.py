"""
Vehicle Parser Agent - Extracts make, model, year from natural language queries.

Uses Claude to parse unstructured text like:
"2019 Ford F-150 3.5L EcoBoost - engine stalls"
Into structured vehicle information.
"""

import json
import logging
import re
from typing import Optional

from ..graph.state import GraphState, VehicleInfo
from ..utils.bedrock import get_bedrock_client

logger = logging.getLogger(__name__)

VEHICLE_PARSER_PROMPT = """You are a vehicle information extractor. Extract vehicle details from the user's query.

Extract the following information if present:
- make: Vehicle manufacturer (e.g., Ford, Toyota, Chevrolet)
- model: Vehicle model (e.g., F-150, Camry, Silverado)
- year: Model year (e.g., 2019, 2020)
- engine: Engine specification if mentioned (e.g., 3.5L EcoBoost, 1.5T, V6)

Rules:
1. If information is not mentioned, set it to null
2. Normalize make names (e.g., "Chevy" -> "Chevrolet", "GMC" stays as "GMC")
3. Year should be a 4-digit number
4. Be case-insensitive when matching

Respond ONLY with a JSON object, no other text:
{
    "make": "string or null",
    "model": "string or null",
    "year": number or null,
    "engine": "string or null"
}

User query: {query}
"""


def parse_vehicle_with_regex(query: str) -> VehicleInfo:
    """
    Attempt to parse vehicle info using regex patterns.
    Used as fallback or for simple queries.
    """
    result = VehicleInfo(make=None, model=None, year=None, engine=None)

    # Common patterns
    year_pattern = r'\b(19|20)\d{2}\b'
    engine_pattern = r'\b(\d+\.\d+[LT]?|\d+\.\d+\s*(?:liter|L)|V\d+|[IV]\d+)\b'

    # Known makes (case-insensitive)
    makes = {
        'ford': 'Ford',
        'chevrolet': 'Chevrolet',
        'chevy': 'Chevrolet',
        'toyota': 'Toyota',
        'honda': 'Honda',
        'nissan': 'Nissan',
        'jeep': 'Jeep',
        'ram': 'Ram',
        'gmc': 'GMC',
        'hyundai': 'Hyundai',
        'subaru': 'Subaru',
        'bmw': 'BMW',
        'mercedes': 'Mercedes-Benz',
        'audi': 'Audi',
        'volkswagen': 'Volkswagen',
        'vw': 'Volkswagen',
        'kia': 'Kia',
        'mazda': 'Mazda',
        'lexus': 'Lexus',
        'acura': 'Acura',
        'infiniti': 'Infiniti',
    }

    # Common models
    models = {
        'f-150': 'F-150', 'f150': 'F-150',
        'f-250': 'F-250', 'f250': 'F-250',
        'silverado': 'Silverado',
        'sierra': 'Sierra',
        'camry': 'Camry',
        'corolla': 'Corolla',
        'civic': 'Civic',
        'accord': 'Accord',
        'cr-v': 'CR-V', 'crv': 'CR-V',
        'rav4': 'RAV4', 'rav-4': 'RAV4',
        'explorer': 'Explorer',
        'escape': 'Escape',
        'mustang': 'Mustang',
        'wrangler': 'Wrangler',
        'grand cherokee': 'Grand Cherokee',
        'tahoe': 'Tahoe',
        'suburban': 'Suburban',
        'altima': 'Altima',
        'rogue': 'Rogue',
    }

    query_lower = query.lower()

    # Extract year
    year_match = re.search(year_pattern, query)
    if year_match:
        result['year'] = int(year_match.group())

    # Extract make
    for key, value in makes.items():
        if key in query_lower:
            result['make'] = value
            break

    # Extract model
    for key, value in models.items():
        if key in query_lower:
            result['model'] = value
            break

    # Extract engine
    engine_match = re.search(engine_pattern, query, re.IGNORECASE)
    if engine_match:
        result['engine'] = engine_match.group()

    return result


def parse_vehicle_with_llm(query: str) -> VehicleInfo:
    """
    Use Claude to extract vehicle information from query.
    """
    try:
        client = get_bedrock_client()
        prompt = VEHICLE_PARSER_PROMPT.format(query=query)

        response = client.invoke_claude(
            prompt=prompt,
            system_prompt="You are a precise JSON extractor. Respond only with valid JSON.",
            max_tokens=256,
            temperature=0.0,
        )

        # Parse JSON response
        # Try to extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response)

        return VehicleInfo(
            make=data.get('make'),
            model=data.get('model'),
            year=data.get('year'),
            engine=data.get('engine'),
        )

    except Exception as e:
        logger.error(f"Error parsing vehicle with LLM: {e}")
        # Fall back to regex parsing
        return parse_vehicle_with_regex(query)


def vehicle_parser_node(state: GraphState) -> GraphState:
    """
    LangGraph node that extracts vehicle information from the query.

    Args:
        state: Current graph state

    Returns:
        Updated state with vehicle_info
    """
    query = state['query']
    logger.info(f"Parsing vehicle info from: {query[:100]}...")

    # First try regex (fast, no API cost)
    regex_result = parse_vehicle_with_regex(query)

    # If we got good results from regex, use them
    if regex_result['make'] and regex_result['model']:
        logger.info(f"Regex parsed: {regex_result}")
        state['vehicle_info'] = regex_result
        return state

    # Otherwise use LLM for more complex parsing
    llm_result = parse_vehicle_with_llm(query)
    logger.info(f"LLM parsed: {llm_result}")

    # Merge results (prefer LLM but fill gaps with regex)
    merged = VehicleInfo(
        make=llm_result.get('make') or regex_result.get('make'),
        model=llm_result.get('model') or regex_result.get('model'),
        year=llm_result.get('year') or regex_result.get('year'),
        engine=llm_result.get('engine') or regex_result.get('engine'),
    )

    state['vehicle_info'] = merged

    # Check if we need clarification
    if not merged.get('make') and not merged.get('model'):
        state['needs_clarification'] = True
        state['clarification_question'] = (
            "I couldn't identify the vehicle from your query. "
            "Could you please specify the year, make, and model? "
            "For example: '2019 Ford F-150'"
        )

    return state
