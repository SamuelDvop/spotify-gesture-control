import time
from collections import deque

from mediapipe.tasks.python.vision import hand_landmarker
from mediapipe.tasks.python.vision import drawing_utils, drawing_styles
from mediapipe.tasks.python.vision.core.image import Image, ImageFormat
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

from config import (
    MODEL_PATH, FINGER_RATIO, ORIENT_THR,
    SWIPE_THR, SWIPE_RESET, DOUBLE_WIN,
)

HandLandmarksConnections = hand_landmarker.HandLandmarksConnections


class Gestos:
    def __init__(self):
        options = hand_landmarker.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=VisionTaskRunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        self.model = hand_landmarker.HandLandmarker.create_from_options(options)

        self._sw = {}
        self._first_frame = {}
        self._hand_last_seen = {}
        self._hand_class = {}
        self._hand_class_cnt = {}

    # ── Medición ──

    @staticmethod
    def _d2(a, b):
        return (a.x - b.x) ** 2 + (a.y - b.y) ** 2

    def _ext(self, lm, tip, mcp):
        hs = self._d2(lm[0], lm[9])
        fd = self._d2(lm[tip], lm[mcp])
        return fd > hs * FINGER_RATIO

    def _thumb_ext(self, lm):
        hs = self._d2(lm[0], lm[9])
        d = self._d2(lm[4], lm[5])
        return d > hs * 0.4

    def _orient(self, lm):
        w = lm[0].y
        m = lm[9].y
        if w > m + ORIENT_THR:
            return 'U'
        if w < m - ORIENT_THR:
            return 'D'
        return '?'

    def _finger_count(self, lm):
        c = 0
        if self._thumb_ext(lm):
            c += 1
        for tip, mcp in [(8, 5), (12, 9), (16, 13), (20, 17)]:
            if self._ext(lm, tip, mcp):
                c += 1
        return c

    def _palm_x(self, lm):
        return (lm[0].x + lm[9].x) / 2

    # ── Gestos básicos ──

    def mano_abierta(self, lm):
        return self._finger_count(lm) >= 4

    def puno_play(self, lm):
        for tip, mcp in [(8, 5), (12, 9), (16, 13), (20, 17)]:
            if self._ext(lm, tip, mcp):
                return False
        return True

    def solo_indice(self, lm):
        if not self._ext(lm, 8, 5):
            return False
        hs = self._d2(lm[0], lm[9])
        for tip, mcp in [(12, 9), (16, 13), (20, 17)]:
            fd = self._d2(lm[tip], lm[mcp])
            if fd > hs * 0.50:
                return False
        return True

    def peace_sign(self, lm):
        if not self._ext(lm, 8, 5):
            return False
        if not self._ext(lm, 12, 9):
            return False
        hs = self._d2(lm[0], lm[9])
        for tip, mcp in [(16, 13), (20, 17)]:
            fd = self._d2(lm[tip], lm[mcp])
            if fd > hs * 0.50:
                return False
        return True

    def dir_indice(self, lm):
        tip = lm[8]
        palm = lm[9]
        if tip.y < palm.y - ORIENT_THR:
            return 'UP'
        if tip.y > palm.y + ORIENT_THR:
            return 'DOWN'
        return None

    # ── Swipe ──

    def _swipe_state(self, label):
        if label not in self._sw:
            self._sw[label] = {
                'px': deque(maxlen=10),
                'dir': None,
                'cnt': {'L': 0, 'R': 0},
                't': 0,
                'ready': True,
            }
        return self._sw[label]

    def detectar_swipe(self, lm, t, label):
        s = self._swipe_state(label)
        px = self._palm_x(lm)
        s['px'].append(px)
        res = None

        if s['ready'] and len(s['px']) >= 8:
            dx = s['px'][-1] - s['px'][0]
            if dx > SWIPE_THR:
                s['cnt']['R'] += 1
                s['ready'] = False
                s['t'] = t
                s['dir'] = 'R'
                s['px'].clear()
            elif dx < -SWIPE_THR:
                s['cnt']['L'] += 1
                s['ready'] = False
                s['t'] = t
                s['dir'] = 'L'
                s['px'].clear()

        elif not s['ready'] and len(s['px']) >= 8:
            dx = s['px'][-1] - s['px'][0]
            if abs(dx) < SWIPE_RESET:
                s['ready'] = True
                s['px'].clear()

        if s['t'] > 0 and t - s['t'] > DOUBLE_WIN:
            s['cnt'] = {'L': 0, 'R': 0}
            s['dir'] = None

        if s['dir'] and s['cnt'][s['dir']] >= 2:
            res = s['dir']
            s['cnt'] = {'L': 0, 'R': 0}
            s['dir'] = None

        return res

    # ── Procesamiento ──

    def process(self, rgb_frame, timestamp_ms):
        img = Image(ImageFormat.SRGB, rgb_frame)
        return self.model.detect_for_video(img, timestamp_ms)

    @staticmethod
    def draw_landmarks(frame, landmarks):
        drawing_utils.draw_landmarks(
            frame, landmarks,
            HandLandmarksConnections.HAND_CONNECTIONS,
            drawing_styles.get_default_hand_landmarks_style(),
            drawing_styles.get_default_hand_connections_style(),
        )
