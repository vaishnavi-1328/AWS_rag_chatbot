#!/usr/bin/env python3
"""
Fetch recalls and complaints data from NHTSA API.

NHTSA API Documentation: https://vpic.nhtsa.dot.gov/api/

This script downloads:
1. Recalls by vehicle make/model/year
2. Complaints by vehicle make/model/year
3. Available vehicle makes and models

Usage:
    python scripts/fetch_nhtsa_data.py --makes Ford,Toyota,Honda --years 2015-2024
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# NHTSA API Base URLs
NHTSA_RECALLS_API = "https://api.nhtsa.gov/recalls/recallsByVehicle"
NHTSA_COMPLAINTS_API = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
NHTSA_VPIC_API = "https://vpic.nhtsa.dot.gov/api/vehicles"

# Rate limiting
REQUEST_DELAY = 0.5  # seconds between requests

# Top 10 vehicle makes to fetch by default
DEFAULT_MAKES = [
    "Ford",
    "Chevrolet",
    "Toyota",
    "Honda",
    "Nissan",
    "Jeep",
    "Ram",
    "GMC",
    "Hyundai",
    "Subaru",
]

# Default year range
DEFAULT_START_YEAR = 2015
DEFAULT_END_YEAR = 2024


def fetch_with_retry(url: str, params: dict, max_retries: int = 3) -> dict:
    """Fetch URL with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
    return {}


def get_models_for_make(make: str, year: int) -> list[str]:
    """Get available models for a make and year from NHTSA VPIC API."""
    url = f"{NHTSA_VPIC_API}/GetModelsForMakeYear/make/{make}/modelyear/{year}"
    params = {"format": "json"}

    try:
        data = fetch_with_retry(url, params)
        models = [item["Model_Name"] for item in data.get("Results", [])]
        return models
    except Exception as e:
        logger.error(f"Error fetching models for {make} {year}: {e}")
        return []


def fetch_recalls(make: str, model: str, year: int) -> list[dict]:
    """Fetch recalls for a specific vehicle."""
    params = {
        "make": make,
        "model": model,
        "modelYear": year,
    }

    try:
        data = fetch_with_retry(NHTSA_RECALLS_API, params)
        recalls = data.get("results", [])

        # Add vehicle info to each recall
        for recall in recalls:
            recall["_vehicle"] = {
                "make": make,
                "model": model,
                "year": year,
            }

        return recalls
    except Exception as e:
        logger.error(f"Error fetching recalls for {year} {make} {model}: {e}")
        return []


def fetch_complaints(make: str, model: str, year: int) -> list[dict]:
    """Fetch complaints for a specific vehicle."""
    params = {
        "make": make,
        "model": model,
        "modelYear": year,
    }

    try:
        data = fetch_with_retry(NHTSA_COMPLAINTS_API, params)
        complaints = data.get("results", [])

        # Add vehicle info to each complaint
        for complaint in complaints:
            complaint["_vehicle"] = {
                "make": make,
                "model": model,
                "year": year,
            }

        return complaints
    except Exception as e:
        logger.error(f"Error fetching complaints for {year} {make} {model}: {e}")
        return []


def fetch_all_data(
    makes: list[str],
    start_year: int,
    end_year: int,
    output_dir: Path,
    max_models_per_make: int = 20,
) -> dict[str, int]:
    """
    Fetch all recalls and complaints for specified makes and years.

    Returns:
        Dictionary with counts of fetched data
    """
    all_recalls = []
    all_complaints = []

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Calculate total iterations for progress bar
    years = list(range(start_year, end_year + 1))

    for make in makes:
        logger.info(f"Fetching data for {make}...")

        for year in tqdm(years, desc=f"{make}", leave=False):
            # Get models for this make/year
            models = get_models_for_make(make, year)

            # Limit models to avoid too many requests
            models = models[:max_models_per_make]

            for model in models:
                # Fetch recalls
                recalls = fetch_recalls(make, model, year)
                all_recalls.extend(recalls)

                # Fetch complaints
                complaints = fetch_complaints(make, model, year)
                all_complaints.extend(complaints)

                # Rate limiting
                time.sleep(REQUEST_DELAY)

        logger.info(f"  {make}: {len([r for r in all_recalls if r['_vehicle']['make'] == make])} recalls, "
                   f"{len([c for c in all_complaints if c['_vehicle']['make'] == make])} complaints")

    # Save to files
    recalls_path = output_dir / "recalls.json"
    complaints_path = output_dir / "complaints.json"

    with open(recalls_path, "w", encoding="utf-8") as f:
        json.dump(all_recalls, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(all_recalls)} recalls to {recalls_path}")

    with open(complaints_path, "w", encoding="utf-8") as f:
        json.dump(all_complaints, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(all_complaints)} complaints to {complaints_path}")

    return {
        "recalls": len(all_recalls),
        "complaints": len(all_complaints),
    }


def create_sample_data(output_dir: Path) -> None:
    """Create sample data for testing without API calls."""
    sample_recalls = [
        {
            "NHTSACampaignNumber": "20V123000",
            "Manufacturer": "Ford Motor Company",
            "Subject": "Fuel Pump May Fail",
            "Component": "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP",
            "Summary": "Ford Motor Company is recalling certain 2018-2020 F-150 vehicles equipped with 3.5L EcoBoost engines. The fuel pump may fail, causing the engine to stall.",
            "Consequence": "A fuel pump failure can cause the engine to stall while driving, increasing the risk of a crash.",
            "Remedy": "Dealers will replace the fuel pump module, free of charge. Owner notification letters are expected to be mailed April 15, 2020.",
            "Notes": "Owners may contact Ford customer service at 1-866-436-7332.",
            "ModelYear": "2019",
            "Make": "FORD",
            "Model": "F-150",
            "_vehicle": {"make": "Ford", "model": "F-150", "year": 2019},
        },
        {
            "NHTSACampaignNumber": "21V456000",
            "Manufacturer": "Ford Motor Company",
            "Subject": "Windshield Wiper Motor May Fail",
            "Component": "VISIBILITY:WINDSHIELD WIPER/WASHER:MOTOR",
            "Summary": "Ford Motor Company is recalling certain 2020-2021 Explorer vehicles. The windshield wiper motor may fail.",
            "Consequence": "Loss of windshield wiper function can reduce visibility during rain, increasing the risk of a crash.",
            "Remedy": "Dealers will replace the windshield wiper motor, free of charge.",
            "Notes": "",
            "ModelYear": "2020",
            "Make": "FORD",
            "Model": "EXPLORER",
            "_vehicle": {"make": "Ford", "model": "Explorer", "year": 2020},
        },
        {
            "NHTSACampaignNumber": "19V789000",
            "Manufacturer": "Toyota Motor Engineering & Manufacturing",
            "Subject": "Fuel Pump Impeller May Deform",
            "Component": "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP",
            "Summary": "Toyota is recalling certain 2018-2019 Camry vehicles. The fuel pump impeller may deform, causing the fuel pump to fail.",
            "Consequence": "If the fuel pump fails, the engine may stall or may not start, increasing the risk of a crash.",
            "Remedy": "Dealers will replace the fuel pump, free of charge.",
            "Notes": "",
            "ModelYear": "2019",
            "Make": "TOYOTA",
            "Model": "CAMRY",
            "_vehicle": {"make": "Toyota", "model": "Camry", "year": 2019},
        },
        {
            "NHTSACampaignNumber": "22V111000",
            "Manufacturer": "General Motors LLC",
            "Subject": "Brake Fluid Leak",
            "Component": "SERVICE BRAKES, HYDRAULIC:FOUNDATION COMPONENTS:MASTER CYLINDER",
            "Summary": "General Motors is recalling certain 2019-2022 Silverado 1500 vehicles. The brake master cylinder may develop a leak.",
            "Consequence": "A brake fluid leak can result in reduced braking performance, increasing the risk of a crash.",
            "Remedy": "Dealers will replace the brake master cylinder, free of charge.",
            "Notes": "",
            "ModelYear": "2020",
            "Make": "CHEVROLET",
            "Model": "SILVERADO 1500",
            "_vehicle": {"make": "Chevrolet", "model": "Silverado 1500", "year": 2020},
        },
        {
            "NHTSACampaignNumber": "23V222000",
            "Manufacturer": "Honda",
            "Subject": "Fuel Pump Failure",
            "Component": "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP",
            "Summary": "Honda is recalling certain 2019-2020 CR-V vehicles with 1.5L turbocharged engines. The fuel pump may fail.",
            "Consequence": "Engine stall while driving increases the risk of a crash.",
            "Remedy": "Dealers will replace the fuel pump, free of charge.",
            "Notes": "",
            "ModelYear": "2019",
            "Make": "HONDA",
            "Model": "CR-V",
            "_vehicle": {"make": "Honda", "model": "CR-V", "year": 2019},
        },
    ]

    sample_complaints = [
        {
            "odiNumber": "11234567",
            "manufacturer": "Ford Motor Company",
            "crash": "N",
            "fire": "N",
            "numberOfInjuries": 0,
            "numberOfDeaths": 0,
            "dateOfIncident": "2020-03-15",
            "dateComplaintFiled": "2020-03-20",
            "vin": "1FTEW1*********",
            "components": "ENGINE",
            "summary": "While driving at highway speed, the engine suddenly lost power and stalled. The check engine light came on. Had to coast to the shoulder. Restarted after 5 minutes but hesitated. Dealer said fuel pump was failing.",
            "products": [{"productMake": "FORD", "productModel": "F-150", "productYear": 2019}],
            "_vehicle": {"make": "Ford", "model": "F-150", "year": 2019},
        },
        {
            "odiNumber": "11234568",
            "manufacturer": "Ford Motor Company",
            "crash": "N",
            "fire": "N",
            "numberOfInjuries": 0,
            "numberOfDeaths": 0,
            "dateOfIncident": "2021-06-10",
            "dateComplaintFiled": "2021-06-15",
            "vin": "1FMSK*********",
            "components": "VISIBILITY:WINDSHIELD WIPER/WASHER",
            "summary": "Windshield wipers stopped working during heavy rain on the highway. Very dangerous situation. Had to pull over immediately.",
            "products": [{"productMake": "FORD", "productModel": "EXPLORER", "productYear": 2020}],
            "_vehicle": {"make": "Ford", "model": "Explorer", "year": 2020},
        },
        {
            "odiNumber": "11234569",
            "manufacturer": "General Motors LLC",
            "crash": "N",
            "fire": "N",
            "numberOfInjuries": 0,
            "numberOfDeaths": 0,
            "dateOfIncident": "2022-01-20",
            "dateComplaintFiled": "2022-01-25",
            "vin": "3GCUY*********",
            "components": "POWER TRAIN:AUTOMATIC TRANSMISSION",
            "summary": "Transmission shudders and jerks when accelerating from a stop. Feels like the truck is slipping. Dealer said this is normal for the 8-speed transmission but it doesn't feel right.",
            "products": [{"productMake": "CHEVROLET", "productModel": "SILVERADO 1500", "productYear": 2020}],
            "_vehicle": {"make": "Chevrolet", "model": "Silverado 1500", "year": 2020},
        },
        {
            "odiNumber": "11234570",
            "manufacturer": "Toyota Motor Engineering & Manufacturing",
            "crash": "N",
            "fire": "N",
            "numberOfInjuries": 0,
            "numberOfDeaths": 0,
            "dateOfIncident": "2020-08-05",
            "dateComplaintFiled": "2020-08-10",
            "vin": "4T1B1*********",
            "components": "ENGINE",
            "summary": "Car stalled at a red light. Would not restart for several minutes. When it finally started, the engine ran rough. Dealer found fuel pump was defective.",
            "products": [{"productMake": "TOYOTA", "productModel": "CAMRY", "productYear": 2019}],
            "_vehicle": {"make": "Toyota", "model": "Camry", "year": 2019},
        },
        {
            "odiNumber": "11234571",
            "manufacturer": "Honda",
            "crash": "N",
            "fire": "N",
            "numberOfInjuries": 0,
            "numberOfDeaths": 0,
            "dateOfIncident": "2021-02-28",
            "dateComplaintFiled": "2021-03-05",
            "vin": "2HKRW*********",
            "components": "ENGINE AND ENGINE COOLING",
            "summary": "Oil dilution issue. Oil smells like gasoline and level keeps rising above full mark. Dealer says it's a known issue with the 1.5T engine in cold climates.",
            "products": [{"productMake": "HONDA", "productModel": "CR-V", "productYear": 2019}],
            "_vehicle": {"make": "Honda", "model": "CR-V", "year": 2019},
        },
    ]

    # Create sample directory
    sample_dir = output_dir / "sample"
    sample_dir.mkdir(parents=True, exist_ok=True)

    # Save sample data
    with open(sample_dir / "sample_recalls.json", "w", encoding="utf-8") as f:
        json.dump(sample_recalls, f, indent=2)
    logger.info(f"Created sample recalls at {sample_dir / 'sample_recalls.json'}")

    with open(sample_dir / "sample_complaints.json", "w", encoding="utf-8") as f:
        json.dump(sample_complaints, f, indent=2)
    logger.info(f"Created sample complaints at {sample_dir / 'sample_complaints.json'}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch NHTSA recalls and complaints data"
    )
    parser.add_argument(
        "--makes",
        type=str,
        default=",".join(DEFAULT_MAKES),
        help="Comma-separated list of vehicle makes",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_START_YEAR,
        help="Start year (inclusive)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=DEFAULT_END_YEAR,
        help="End year (inclusive)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Output directory for downloaded data",
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Only create sample data (no API calls)",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        default=20,
        help="Maximum models to fetch per make/year",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.sample_only:
        logger.info("Creating sample data only (no API calls)...")
        create_sample_data(output_dir.parent)
        return

    makes = [m.strip() for m in args.makes.split(",")]

    logger.info(f"Fetching data for makes: {makes}")
    logger.info(f"Year range: {args.start_year} - {args.end_year}")
    logger.info(f"Output directory: {output_dir}")

    counts = fetch_all_data(
        makes=makes,
        start_year=args.start_year,
        end_year=args.end_year,
        output_dir=output_dir,
        max_models_per_make=args.max_models,
    )

    logger.info(f"Fetch complete! Total: {counts['recalls']} recalls, {counts['complaints']} complaints")

    # Also create sample data for testing
    create_sample_data(output_dir.parent)


if __name__ == "__main__":
    main()
