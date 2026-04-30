"""
Spotify authentication.

Uses the Spotipy library with the OAuth Authorization Code flow, which is
required for user-specific endpoints like top artists and top tracks.

How it works:
  1. On first run, `get_client()` opens a browser tab to Spotify's authorisation
     page. The user logs in and grants consent.
  2. Spotify redirects to the configured SPOTIFY_REDIRECT_URI (default:
     http://localhost:8888/callback) with a short-lived authorisation code.
  3. Spotipy exchanges the code for an access token + refresh token and caches
     them to `.spotify_cache` so subsequent runs skip the browser step.
  4. When the access token expires (1 hour), Spotipy silently refreshes it
     using the cached refresh token.

Required environment variables (set in .env at the project root):
  SPOTIFY_CLIENT_ID      — Client ID from your Spotify Developer app
  SPOTIFY_CLIENT_SECRET  — Client Secret from your Spotify Developer app
  SPOTIFY_REDIRECT_URI   — Must match the Redirect URI registered in the
                           Spotify Developer Dashboard. Defaults to
                           http://localhost:8888/callback.

Setting up a Spotify Developer app:
  1. Go to https://developer.spotify.com/dashboard and create a new app.
  2. Add http://localhost:8888/callback as a Redirect URI in the app settings.
  3. Copy the Client ID and Client Secret into your .env file.
"""
import os
from pathlib import Path
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

# OAuth scopes required across all ingestion endpoints.
SCOPES = "user-top-read user-read-recently-played"

# Absolute path so the cache is in the same place whether run locally or via Dagster.
_CACHE_PATH = Path(__file__).parent.parent / ".spotify_cache"


def get_client() -> spotipy.Spotify:
    """Return an authenticated Spotipy client.

    On first call this triggers an interactive OAuth browser flow. Subsequent
    calls use the cached token at `.spotify_cache` and refresh silently.
    """
    auth_manager = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"),
        scope=SCOPES,
        cache_path=str(_CACHE_PATH),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)
