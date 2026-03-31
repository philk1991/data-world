import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

SCOPES = "user-top-read"


def get_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"),
        scope=SCOPES,
        cache_path=".spotify_cache",
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)
