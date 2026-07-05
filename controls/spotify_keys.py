import time

import win32api
import win32con
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from ctypes import cast, POINTER

from config import VK_NEXT, VK_PREV, VK_PLAY, VOL_STEP


class SpotifyControl:
    def __init__(self):
        self._vol = None
        try:
            dev = AudioUtilities.GetSpeakers()
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._vol = cast(iface, POINTER(IAudioEndpointVolume))
        except Exception:
            pass

    def _key(self, vk):
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)

    def next_track(self):
        print("[Spotify] Siguiente canción")
        self._key(VK_NEXT)

    def prev_track(self):
        print("[Spotify] Canción anterior")
        self._key(VK_PREV)

    def toggle_play(self):
        print("[Spotify] Play / Pause")
        self._key(VK_PLAY)

    def vol_up(self):
        if self._vol:
            cur = self._vol.GetMasterVolumeLevelScalar()
            nv = min(1.0, cur + VOL_STEP)
            self._vol.SetMasterVolumeLevelScalar(nv, None)
        self._spotify_vol(0.04)

    def vol_down(self):
        if self._vol:
            cur = self._vol.GetMasterVolumeLevelScalar()
            nv = max(0.0, cur - VOL_STEP)
            self._vol.SetMasterVolumeLevelScalar(nv, None)
        self._spotify_vol(-0.04)

    def _spotify_vol(self, delta):
        try:
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                if s.Process and s.Process.name() == "Spotify.exe":
                    vol = s.SimpleAudioVolume
                    cur = vol.GetMasterVolume()
                    nv = max(0.0, min(1.0, cur + delta))
                    vol.SetMasterVolume(nv, None)
        except:
            pass

    def get_vol_pct(self):
        if self._vol:
            return int(self._vol.GetMasterVolumeLevelScalar() * 100)
        return 0
