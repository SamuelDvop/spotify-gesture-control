import json
import time
import threading
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import (
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI, TOKEN_CACHE_FILE,
)


class SpotifyAPI:
    def __init__(self):
        self._sp = None
        self._last_track = {}
        self._album_art_url = None
        self._album_art = None
        self._progress_ms = 0
        self._duration_ms = 0
        self._is_playing = False
        self._liked = False
        self._error = None
        self._ready = False

        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            self._error = "SPOTIFY_CLIENT_ID / SPOTIFY_SECRET no configurados"
            print(f"[!] {self._error}")
            return

        try:
            self._sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="user-read-currently-playing user-read-playback-state user-modify-playback-state",
                open_browser=True,
                cache_path=TOKEN_CACHE_FILE,
            ))
            self._ready = True
            print("[Spotify API] Conectado")
        except Exception as e:
            self._error = str(e)
            print(f"[!] Spotify API error: {e}")

    @property
    def ready(self):
        return self._ready

    @property
    def error(self):
        return self._error

    @property
    def album_art_url(self):
        return self._album_art_url

    @property
    def album_art(self):
        return self._album_art

    @album_art.setter
    def album_art(self, img):
        self._album_art = img

    def update(self):
        if not self._ready:
            return
        try:
            playback = self._sp.current_playback()
            if playback is None or playback.get("item") is None:
                self._is_playing = False
                return

            item = playback["item"]
            track_id = item["id"]

            self._last_track = {
                "id": track_id,
                "name": item.get("name", "?"),
                "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                "album": item.get("album", {}).get("name", ""),
            }
            self._album_art_url = item["album"]["images"][0]["url"] if item.get("album", {}).get("images") else None
            self._progress_ms = playback.get("progress_ms", 0)
            self._duration_ms = item.get("duration_ms", 1)
            self._is_playing = playback.get("is_playing", False)

            # Check if already liked
            saved = self._sp.current_user_saved_tracks_contains([track_id])
            self._liked = saved[0] if saved else False

        except Exception as e:
            print(f"[!] Error actualizando playback: {e}")

    @property
    def track_name(self):
        return self._last_track.get("name", "")

    @property
    def track_artist(self):
        return self._last_track.get("artist", "")

    @property
    def progress_ms(self):
        return self._progress_ms

    @property
    def duration_ms(self):
        return self._duration_ms

    @property
    def is_playing(self):
        return self._is_playing

    @property
    def liked(self):
        return self._liked

    def toggle_like(self):
        if not self._ready or not self._last_track.get("id"):
            return None
        try:
            track_id = self._last_track["id"]
            if self._liked:
                self._sp.current_user_saved_tracks_delete([track_id])
                self._liked = False
                print(f"[Spotify] Unlike: {self._last_track['name']}")
                return False
            else:
                self._sp.current_user_saved_tracks_add([track_id])
                self._liked = True
                print(f"[Spotify] Like: {self._last_track['name']}")
                return True
        except Exception as e:
            print(f"[!] Error toggling like: {e}")
            return None
