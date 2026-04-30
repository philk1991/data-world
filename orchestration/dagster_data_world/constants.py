import sys
from pathlib import Path

# Absolute paths relative to this file's location:
#   constants.py → dagster_data_world/ → orchestration/ → data-world/
PROJECT_ROOT = Path(__file__).parent.parent.parent
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt"
DATA_DIR = PROJECT_ROOT / "data"
DATA_INGESTION_DIR = PROJECT_ROOT / "data-ingestion"
SPOTIFY_CACHE_PATH = PROJECT_ROOT / ".spotify_cache"

DUCKDB_PATH = str(DATA_DIR / "spotify.duckdb")
CRYPTO_DUCKDB_PATH = str(DATA_DIR / "crypto_raw.duckdb")

# Make data-ingestion packages importable (spotify, statsbomb, crypto)
if str(DATA_INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_INGESTION_DIR))
