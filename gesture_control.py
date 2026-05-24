import cv2
import time
from collections import deque
import os
import sys

# Suprimir warnings no-críticos de MediaPipe en stderr
_orig_stderr = sys.stderr
class _StderrFilter:
    def write(self, s):
        if 'clearcut' in s or 'landmark_projection' in s or 'portable_' in s:
            return
        _orig_stderr.write(s)
    def flush(self):
        _orig_stderr.flush()
sys.stderr = _StderrFilter()

import win32api
import win32con
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from ctypes import cast, POINTER

from mediapipe.tasks.python.vision import hand_landmarker
from mediapipe.tasks.python.vision import drawing_utils, drawing_styles
from mediapipe.tasks.python.vision.core.image import Image, ImageFormat
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

HandLandmarksConnections = hand_landmarker.HandLandmarksConnections


# ─── CONFIGURACION ──────────────────────────────────────────────────────────

CAM_ID = 0
FRAME_W = 640
FRAME_H = 480

MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "hand_landmarker.task"
)

VK_NEXT = 0xB0
VK_PREV = 0xB1
VK_PLAY = 0xB3

SWIPE_THR = 0.08
SWIPE_RESET = 0.03
DOUBLE_WIN = 1.2
PP_COOLDOWN = 0.8
VOL_COOLDOWN = 0.08
VOL_STEP = 0.04
FINGER_RATIO = 0.35
ORIENT_THR = 0.03


# ─── CONTROLADOR SPOTIFY ────────────────────────────────────────────────────

class SpotifyControl:
    def __init__(self):
        self._vol = None
        try:
            dev = AudioUtilities.GetSpeakers()
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._vol = cast(iface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            print(f"[!] Control de volumen no disponible: {e}")

    def _key(self, vk):
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)

    def next_track(self):
        print("[Spotify] Siguiente cancion")
        self._key(VK_NEXT)

    def prev_track(self):
        print("[Spotify] Cancion anterior")
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


# ─── RECONOCEDOR DE GESTOS ──────────────────────────────────────────────────

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

    # ── Mediciones ──

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

    # ── Gestos ──

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

    # ── Procesamiento de frame ──

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


# ─── MAIN ───────────────────────────────────────────────────────────────────

def main():
    cap = cv2.VideoCapture(CAM_ID)
    if not cap.isOpened():
        print("Error: No se pudo abrir la camara.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    g = Gestos()
    s = SpotifyControl()

    pp_t = 0.0
    vol_t = 0.0
    vol_last_dir = None
    vol_last_t = 0.0
    prev_hand_mode = None
    last_unanimous = None
    first_stable = None
    toggle_notif = None
    toggle_notif_t = 0.0
    vol_activo = False

    print("=" * 52)
    print("  CONTROL POR GESTOS  -  SPOTIFY")
    print("=" * 52)
    print("  Mano abierta            ->  Play")
    print("  Pu\u00f1o                   ->  Pausa")
    print("  \u00cdndice arriba           ->  Subir volumen")
    print("  \u00cdndice abajo            ->  Bajar volumen")
    print("  Deslizar der. (x2)      ->  Siguiente canci\u00f3n")
    print("  Deslizar izq. (x2)      ->  Canci\u00f3n anterior")
    print("")
    print("  [ESC] para salir")
    print("=" * 52)

    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                print("Error leyendo camara.")
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            t = time.time()
            timestamp_ms = int(t * 1000)
            H, W = frame.shape[:2]
            accion = False

            result = g.process(rgb, timestamp_ms)

            # Notificación de toggle (dura 1s)
            notif_alpha = max(0, 1 - (t - toggle_notif_t) / 1.0) if toggle_notif else 0
            if notif_alpha > 0:
                if toggle_notif == 'PLAY \u25b6':
                    notif_color = (0, 255, 100)
                elif toggle_notif == 'PAUSA \u23f8':
                    notif_color = (255, 150, 150)
                else:
                    notif_color = (200, 200, 0)
                cv2.putText(frame, toggle_notif, (W // 2 - 60, H // 2 - 60),
                            cv2.FONT_HERSHEY_DUPLEX, 1.0, notif_color,
                            max(2, int(notif_alpha * 5)))

            cv2.putText(frame, "[ESC] Salir", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

            if result and result.hand_landmarks:
                now_frame = time.time()
                fist_count = 0
                open_count = 0
                index_count = 0
                other_count = 0

                vol_activo = False

                for i in range(len(result.hand_landmarks)):
                    lm = result.hand_landmarks[i]
                    label = result.handedness[i][0].category_name

                    # Corregir handedness porque el frame está espejado
                    label = 'Right' if label == 'Left' else 'Left'

                    g._hand_last_seen[label] = now_frame
                    first_frame = label not in g._first_frame
                    g._first_frame[label] = True

                    g.draw_landmarks(frame, lm)
                    fc = g._finger_count(lm)

                    # Posicion base para overlays de esta mano
                    y = 80 + i * 90

                    # ── Nombre mano + dedos ──
                    cv2.putText(frame, f"{label}: {fc} dedos", (10, y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 2)

                    # ── Swipe ──
                    sw = g.detectar_swipe(lm, t, label)
                    if sw and not accion:
                        if sw == 'R':
                            s.next_track()
                            accion = True
                        elif sw == 'L':
                            s.prev_track()
                            accion = True

                    # ── Clasificar mano para estabilidad ──
                    if g.solo_indice(lm):
                        cl = 'index'
                    elif g.puno_play(lm):
                        cl = 'fist'
                    elif g.mano_abierta(lm):
                        cl = 'open'
                    else:
                        cl = 'other'

                    prev_cl = g._hand_class.get(label)
                    if cl == prev_cl:
                        g._hand_class_cnt[label] = g._hand_class_cnt.get(label, 0) + 1
                    else:
                        g._hand_class_cnt[label] = 1
                    g._hand_class[label] = cl

                    # Solo contar si es estable (2+ frames iguales) y no primer frame
                    estable = g._hand_class_cnt.get(label, 0) >= 2

                    # ── Contar para play/pause y volumen ──
                    if not first_frame and estable:
                        if cl == 'index':
                            d = g.dir_indice(lm)
                            if d is None:
                                d = vol_last_dir
                            if d == 'UP' and t - vol_t > VOL_COOLDOWN:
                                s.vol_up()
                                vol_t = t
                                vol_last_dir = 'UP'
                                vol_last_t = t
                            elif d == 'DOWN' and t - vol_t > VOL_COOLDOWN:
                                s.vol_down()
                                vol_t = t
                                vol_last_dir = 'DOWN'
                                vol_last_t = t
                        elif cl == 'fist':
                            fist_count += 1
                        elif cl == 'open':
                            open_count += 1
                    if cl == 'index':
                        vol_activo = True
                        if not first_frame and estable:
                            index_count += 1
                    elif not first_frame and estable and cl == 'other':
                        other_count += 1

                    # ── Overlay de gesto detectado ──
                    if g.mano_abierta(lm):
                        cv2.putText(frame, "\u25b6  PLAY", (10, y + 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 100), 2)
                    elif g.puno_play(lm):
                        cv2.putText(frame, "\u23f8  PAUSA", (10, y + 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 255), 2)
                    elif g.solo_indice(lm):
                        d = g.dir_indice(lm) or vol_last_dir
                        if d == 'UP':
                            cv2.putText(frame, "\u2191  SUBIR VOLUMEN", (10, y + 25),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                        elif d == 'DOWN':
                            cv2.putText(frame, "\u2193  BAJAR VOLUMEN", (10, y + 25),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                        else:
                            cv2.putText(frame, "\u25cb  INDICE", (10, y + 25),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

                # ── Play / Pause: transición entre modos de mano ──
                manos_claras = fist_count + open_count
                manos_ocupadas = index_count + other_count

                if len(result.hand_landmarks) == 0:
                    cur_mode = 'none'
                elif manos_claras > 0 and manos_ocupadas == 0:
                    # TODAS las manos estables hacen solo fist o solo open
                    if fist_count > 0 and open_count == 0:
                        cur_mode = 'fist'
                    elif open_count > 0 and fist_count == 0:
                        cur_mode = 'open'
                    else:
                        cur_mode = 'mixed'  # no debería pasar
                else:
                    cur_mode = 'mixed'

                # Primer modo estable: registrar sin togglear
                if first_stable is None and cur_mode not in ('none', 'mixed'):
                    first_stable = cur_mode
                    last_unanimous = cur_mode
                    prev_hand_mode = cur_mode
                    toggle_notif = 'GESTO REGISTRADO'
                    toggle_notif_t = t
                elif not accion and t - pp_t > PP_COOLDOWN and prev_hand_mode is not None:
                    if cur_mode == 'fist' and prev_hand_mode not in ('fist', 'none', 'mixed'):
                        s.toggle_play()
                        pp_t = t
                        accion = True
                        toggle_notif = 'PAUSA \u23f8'
                        toggle_notif_t = t
                        last_unanimous = 'fist'
                    elif cur_mode == 'open' and prev_hand_mode not in ('open', 'none', 'mixed'):
                        s.toggle_play()
                        pp_t = t
                        accion = True
                        toggle_notif = 'PLAY \u25b6'
                        toggle_notif_t = t
                        last_unanimous = 'open'
                    elif cur_mode == 'fist' and prev_hand_mode == 'mixed' and manos_ocupadas == 0 and last_unanimous != 'fist':
                        s.toggle_play()
                        pp_t = t
                        accion = True
                        toggle_notif = 'PAUSA \u23f8'
                        toggle_notif_t = t
                        last_unanimous = 'fist'
                    elif cur_mode == 'open' and prev_hand_mode == 'mixed' and manos_ocupadas == 0 and last_unanimous != 'open':
                        s.toggle_play()
                        pp_t = t
                        accion = True
                        toggle_notif = 'PLAY \u25b6'
                        toggle_notif_t = t
                        last_unanimous = 'open'

                if prev_hand_mode is None or cur_mode != prev_hand_mode:
                    prev_hand_mode = cur_mode

                # ── Limpieza manos que desaparecieron ──
                stale = [h for h in g._first_frame if now_frame - g._hand_last_seen.get(h, 0) > 2]
                for h in stale:
                    del g._first_frame[h]
                    g._hand_class.pop(h, None)
                    g._hand_class_cnt.pop(h, None)

            # ── Volumen ──
            if s._vol:
                vol_pct = int(s._vol.GetMasterVolumeLevelScalar() * 100)

                # Color según nivel
                if vol_pct < 30:
                    vol_color = (0, 255, 100)
                elif vol_pct < 60:
                    vol_color = (0, 230, 255)
                elif vol_pct < 85:
                    vol_color = (255, 200, 0)
                else:
                    vol_color = (255, 50, 50)

                bar_w = 300
                bar_h = 22
                bar_x = (W - bar_w) // 2
                bar_y = H - 50
                fill = int(bar_w * vol_pct / 100)

                # Flash cambio (centro)
                flash_alpha = max(0, 1 - (t - vol_last_t) / 0.6) if vol_last_dir else 0
                if flash_alpha > 0:
                    flash_label = f"+ {vol_pct}%" if vol_last_dir == 'UP' else f"\u2212 {vol_pct}%"
                    flash_color = (0, 255, 200) if vol_last_dir == 'UP' else (255, 200, 0)
                    fs = int(40 + flash_alpha * 40)
                    # Sombra
                    cv2.putText(frame, flash_label, (W // 2 + 3, H // 2 - 57),
                                cv2.FONT_HERSHEY_DUPLEX, fs / 20, (0, 0, 0),
                                max(5, int(flash_alpha * 7)))
                    # Texto
                    cv2.putText(frame, flash_label, (W // 2, H // 2 - 60),
                                cv2.FONT_HERSHEY_DUPLEX, fs / 20, flash_color,
                                max(3, int(flash_alpha * 5)))

                # Barra fondo
                cv2.rectangle(frame, (bar_x, bar_y),
                              (bar_x + bar_w, bar_y + bar_h),
                              (30, 30, 30), -1)
                # Barra llena con borde redondeado simulado
                if fill > 4:
                    cv2.rectangle(frame, (bar_x, bar_y),
                                  (bar_x + fill, bar_y + bar_h),
                                  vol_color, -1)
                # Borde exterior
                cv2.rectangle(frame, (bar_x, bar_y),
                              (bar_x + bar_w, bar_y + bar_h),
                              (60, 60, 60), 1)
                # Porcentaje DENTRO de la barra
                cv2.putText(frame, f"VOLUMEN  {vol_pct}%",
                            (bar_x + 10, bar_y + 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                # Dirección activa
                if vol_activo and t - vol_last_t < 0.5:
                    d_text = "SUBIR \u25b2" if vol_last_dir == 'UP' else "BAJAR \u25bc"
                    d_color = (0, 255, 200) if vol_last_dir == 'UP' else (255, 200, 0)
                    cv2.putText(frame, d_text, (bar_x + bar_w + 12, bar_y + 16),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, d_color, 2)
                elif vol_activo:
                    cv2.putText(frame, "INDICE \u25c9", (bar_x + bar_w + 12, bar_y + 16),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

            cv2.imshow("Control por gestos - Spotify", frame)

            if cv2.waitKey(1) & 0xFF == 27:
                break

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Programa terminado.")


if __name__ == "__main__":
    main()
