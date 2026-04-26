#!/usr/bin/env python3
"""
One-time setup: index the Employment Standards Act of Ontario into ChromaDB.

Run this once after initial setup, before starting the API or Streamlit:

    python setup_act.py

The ESA text is stored permanently in the chroma_db directory and shared
across all contract analyses. Re-run with --force to re-index.
"""

import sys
import argparse
from pathlib import Path

# Add project root so backend imports resolve
sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(description="Index the ESA reference text into ChromaDB.")
    parser.add_argument("--force", action="store_true", help="Re-index even if already done")
    args = parser.parse_args()

    print("Employment Standards Act of Ontario — Reference Indexer")
    print("=" * 60)

    from backend.ingestion.act_ingestor import ingest_eao_act, act_collection_exists
    from backend.config import settings

    if act_collection_exists() and not args.force:
        print(f"[OK] ESA act collection already indexed at '{settings.chroma_persist_dir}'")
        print("     Use --force to re-index.")
        return

    print(f"Indexing ESA sections into ChromaDB at '{settings.chroma_persist_dir}'...")
    print("This may take 20-60 seconds (embedding model loading + vectorization).\n")

    from backend.observability.logger import configure_logging
    configure_logging()

    count = ingest_eao_act(force=args.force)

    print(f"\n[OK] Successfully indexed {count} ESA sections.")
    print(f"     Collection: '{settings.esa_act_collection_name}'")
    print("\nYou can now start the API server and Streamlit frontend.")


if __name__ == "__main__":
    main()
