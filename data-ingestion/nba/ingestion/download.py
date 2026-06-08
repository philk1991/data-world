"""
Download individual files from the Kaggle NBA dataset.

Source: https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores

Files are fetched one at a time via kagglehub so we pull only the files we load
(core + extended box scores) and skip the multi-GB PlaybyPlay.parquet entirely.

Authentication: kagglehub reads credentials from the KAGGLE_USERNAME / KAGGLE_KEY
environment variables (set in the project .env) or from ~/.kaggle/kaggle.json.
Create a token at https://www.kaggle.com/settings → "Create New Token".
"""
import kagglehub

DATASET_HANDLE = "eoinamoore/historical-nba-data-and-player-box-scores"


def download_file(filename: str) -> str | None:
    """Download a single file from the dataset and return its local path.

    Returns None on failure (e.g. missing credentials) so the caller can skip
    the file rather than aborting the whole run.
    """
    try:
        return kagglehub.dataset_download(DATASET_HANDLE, path=filename)
    except Exception as e:
        print(f"  Warning: could not download {filename}: {e}")
        print("  Check KAGGLE_USERNAME / KAGGLE_KEY in your .env "
              "(create a token at https://www.kaggle.com/settings).")
        return None
