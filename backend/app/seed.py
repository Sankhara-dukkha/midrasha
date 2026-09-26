"""Load the seed catalogue into the configured database: `python -m app.seed`."""

import json
from pathlib import Path

from app.db import get_sessionmaker
from app.services.catalog import load_catalog

CATALOG_PATH = Path(__file__).resolve().parents[2] / "db" / "seeds" / "catalog.json"


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    with get_sessionmaker()() as db:
        load_catalog(db, catalog)
    print(f"Loaded {len(catalog['resources'])} resources, {len(catalog['templates'])} templates")


if __name__ == "__main__":
    main()
