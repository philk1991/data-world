import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dagster import ConfigurableResource

from dagster_data_world.constants import SPOTIFY_CACHE_PATH

_SCOPES = "user-top-read user-read-recently-played"


class SpotifyClientResource(ConfigurableResource):
    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:8888/callback"
    cache_path: str = str(SPOTIFY_CACHE_PATH)

    def get_client(self) -> spotipy.Spotify:
        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=_SCOPES,
            cache_path=self.cache_path,
            open_browser=True,
        )
        return spotipy.Spotify(auth_manager=auth_manager)
