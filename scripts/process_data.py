#!/usr/bin/env python3
"""
Process raw NHTSA data into a unified document format for RAG.

This script:
1. Loads raw recalls and complaints JSON files
2. Normalizes them into a consistent document schema
3. Creates text chunks optimized for embedding/retrieval
4. Saves processed documents for indexing
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Process NHTSA data into RAG-friendly documents."""

    def __init__(self):
        self.documents = []

    def process_recall(self, recall: dict) -> dict:
        """Convert a recall record into a document."""
        vehicle = recall.get("_vehicle", {})

        # Build searchable text
        text_parts = [
            f"RECALL: {recall.get('Subject', 'Unknown')}",
            f"Campaign Number: {recall.get('NHTSACampaignNumber', 'N/A')}",
            f"Vehicle: {vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}",
            f"Component: {recall.get('Component', 'Unknown')}",
            f"Summary: {recall.get('Summary', '')}",
            f"Consequence: {recall.get('Consequence', '')}",
            f"Remedy: {recall.get('Remedy', '')}",
        ]

        if recall.get("Notes"):
            text_parts.append(f"Notes: {recall.get('Notes')}")

        text = "\n".join(text_parts)

        return {
            "id": f"recall_{recall.get('NHTSACampaignNumber', 'unknown')}",
            "type": "recall",
            "campaign_number": recall.get("NHTSACampaignNumber"),
            "subject": recall.get("Subject"),
            "manufacturer": recall.get("Manufacturer"),
            "component": recall.get("Component"),
            "summary": recall.get("Summary"),
            "consequence": recall.get("Consequence"),
            "remedy": recall.get("Remedy"),
            "notes": recall.get("Notes"),
            "vehicle": {
                "make": vehicle.get("make", recall.get("Make", "")).title(),
                "model": vehicle.get("model", recall.get("Model", "")).title(),
                "year": int(vehicle.get("year", recall.get("ModelYear", 0))),
            },
            "text": text,  # Full text for embedding
        }

    def process_complaint(self, complaint: dict) -> dict:
        """Convert a complaint record into a document."""
        vehicle = complaint.get("_vehicle", {})

        # Try to get vehicle info from products if not in _vehicle
        if not vehicle and complaint.get("products"):
            product = complaint["products"][0]
            vehicle = {
                "make": product.get("productMake", "").title(),
                "model": product.get("productModel", "").title(),
                "year": product.get("productYear", 0),
            }

        # Build searchable text
        text_parts = [
            f"COMPLAINT: {complaint.get('components', 'General')}",
            f"ODI Number: {complaint.get('odiNumber', 'N/A')}",
            f"Vehicle: {vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}",
            f"Component: {complaint.get('components', 'Unknown')}",
            f"Date of Incident: {complaint.get('dateOfIncident', 'Unknown')}",
            f"Description: {complaint.get('summary', '')}",
        ]

        # Add crash/fire/injury info if relevant
        if complaint.get("crash") == "Y":
            text_parts.append("Note: This complaint involved a crash.")
        if complaint.get("fire") == "Y":
            text_parts.append("Note: This complaint involved a fire.")
        if complaint.get("numberOfInjuries", 0) > 0:
            text_parts.append(f"Injuries reported: {complaint.get('numberOfInjuries')}")

        text = "\n".join(text_parts)

        return {
            "id": f"complaint_{complaint.get('odiNumber', 'unknown')}",
            "type": "complaint",
            "odi_number": complaint.get("odiNumber"),
            "manufacturer": complaint.get("manufacturer"),
            "component": complaint.get("components"),
            "summary": complaint.get("summary"),
            "date_of_incident": complaint.get("dateOfIncident"),
            "date_filed": complaint.get("dateComplaintFiled"),
            "crash": complaint.get("crash") == "Y",
            "fire": complaint.get("fire") == "Y",
            "injuries": complaint.get("numberOfInjuries", 0),
            "deaths": complaint.get("numberOfDeaths", 0),
            "vehicle": {
                "make": vehicle.get("make", "").title(),
                "model": vehicle.get("model", "").title(),
                "year": int(vehicle.get("year", 0)),
            },
            "text": text,
        }

    def load_and_process(self, raw_dir: Path) -> list[dict]:
        """Load raw data and process into documents."""
        documents = []

        # Process recalls
        recalls_path = raw_dir / "recalls.json"
        if recalls_path.exists():
            logger.info(f"Loading recalls from {recalls_path}")
            with open(recalls_path, "r", encoding="utf-8") as f:
                recalls = json.load(f)
            for recall in recalls:
                doc = self.process_recall(recall)
                documents.append(doc)
            logger.info(f"Processed {len(recalls)} recalls")
        else:
            logger.warning(f"Recalls file not found: {recalls_path}")

        # Process complaints
        complaints_path = raw_dir / "complaints.json"
        if complaints_path.exists():
            logger.info(f"Loading complaints from {complaints_path}")
            with open(complaints_path, "r", encoding="utf-8") as f:
                complaints = json.load(f)
            for complaint in complaints:
                doc = self.process_complaint(complaint)
                documents.append(doc)
            logger.info(f"Processed {len(complaints)} complaints")
        else:
            logger.warning(f"Complaints file not found: {complaints_path}")

        # Check for sample data if no raw data found
        if not documents:
            sample_recalls_path = raw_dir.parent / "sample" / "sample_recalls.json"
            sample_complaints_path = raw_dir.parent / "sample" / "sample_complaints.json"

            if sample_recalls_path.exists():
                logger.info(f"Loading sample recalls from {sample_recalls_path}")
                with open(sample_recalls_path, "r", encoding="utf-8") as f:
                    recalls = json.load(f)
                for recall in recalls:
                    doc = self.process_recall(recall)
                    documents.append(doc)

            if sample_complaints_path.exists():
                logger.info(f"Loading sample complaints from {sample_complaints_path}")
                with open(sample_complaints_path, "r", encoding="utf-8") as f:
                    complaints = json.load(f)
                for complaint in complaints:
                    doc = self.process_complaint(complaint)
                    documents.append(doc)

        return documents

    def deduplicate(self, documents: list[dict]) -> list[dict]:
        """Remove duplicate documents based on ID."""
        seen = set()
        unique = []
        for doc in documents:
            if doc["id"] not in seen:
                seen.add(doc["id"])
                unique.append(doc)
        return unique

    def create_statistics(self, documents: list[dict]) -> dict:
        """Generate statistics about the processed documents."""
        stats = {
            "total_documents": len(documents),
            "recalls": len([d for d in documents if d["type"] == "recall"]),
            "complaints": len([d for d in documents if d["type"] == "complaint"]),
            "makes": {},
            "years": {},
            "components": {},
        }

        for doc in documents:
            make = doc["vehicle"]["make"]
            year = doc["vehicle"]["year"]
            component = doc.get("component", "Unknown")

            stats["makes"][make] = stats["makes"].get(make, 0) + 1
            stats["years"][str(year)] = stats["years"].get(str(year), 0) + 1
            stats["components"][component] = stats["components"].get(component, 0) + 1

        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Process NHTSA data into RAG-friendly documents"
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="Directory containing raw NHTSA data",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="Output directory for processed documents",
    )

    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = DocumentProcessor()

    # Load and process
    documents = processor.load_and_process(raw_dir)

    if not documents:
        logger.error("No documents to process! Run fetch_nhtsa_data.py first.")
        return

    # Deduplicate
    documents = processor.deduplicate(documents)
    logger.info(f"After deduplication: {len(documents)} documents")

    # Generate statistics
    stats = processor.create_statistics(documents)
    logger.info(f"Statistics: {json.dumps(stats, indent=2)}")

    # Save processed documents
    output_path = output_dir / "documents.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(documents)} documents to {output_path}")

    # Save statistics
    stats_path = output_dir / "statistics.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Saved statistics to {stats_path}")


if __name__ == "__main__":
    main()
