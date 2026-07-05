import sys
import time
import threading
import queue

import cv2
import numpy as np

from config import PP_COOLDOWN, LIKE_COOLDOWN, VOL_COOLDOWN
from vision.camera import Camera
from vision.gesture import Gestos
from controls.spotify_keys import SpotifyControl
from controls.spotify_api import SpotifyAPI
from controls.voice import VoiceFeedback
from controls.speech import SpeechCommands
from ui.overlay import (
    draw_top_bar, draw_hand_info,
    draw_notification, draw_volume_bar, draw_song_panel, draw_album_art,
)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _stderr_filter():
    _orig = sys.stderr
    class _Filter:
        def write(self, s):
            if any(w in s for w in ('clearcut', 'landmark_projection', 'portable_clearcut', 'inference_feedback', 'Failed to send', 'ResponseInfo')):
                return
            _orig.write(s)
        def flush(self):
            _orig.flush()
    sys.stderr = _Filter()


def _download_album_art(url, api):
    if not HAS_REQUESTS or not url:
        return
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            img_arr = np.frombuffer(resp.content, np.uint8)
            img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            if img is not None:
                api.album_art = img
    except:
        pass


def _notif_color(text):
    if "UNLIKE" in text or "LIKE" in text: return (180, 100, 200)
    if "PAUSA" in text: return (60, 60, 230)
    if "PLAY" in text: return (80, 220, 50)
    if "SIGUIENTE" in text: return (230, 170, 70)
    if "ANTERIOR" in text: return (40, 200, 240)
    if "REGISTRADO" in text: return (200, 100, 150)
    return (200, 200, 200)


def main():
    _stderr_filter()

    print("=" * 52)
    print("  CONTROL POR GESTOS  —  SPOTIFY")
    print("=" * 52)
    print("  ✋ Abierta          →  Play")
    print("  ✊ Puño             →  Pausa")
    print("  ☝️ Índice arriba    →  Subir volumen")
    print("  ☝️ Índice abajo     →  Bajar volumen")
    print("  ✌️ Paz              →  Like / Unlike")
    print("  →→ Deslizar (x2)    →  Siguiente canción")
    print("  ←← Deslizar (x2)    →  Canción anterior")
    print()
    print("  [ESC] para salir")
    print("=" * 52)

    try:
        cam = Camera()
    except RuntimeError as e:
        print(f"Error: {e}")
        return

    g = Gestos()
    keys = SpotifyControl()
    api = SpotifyAPI()
    voice = VoiceFeedback()
    cmd_queue = queue.Queue()
    speech = SpeechCommands(lambda c: cmd_queue.put(c))

    pp_t = 0.0
    like_t = 0.0
    vol_t = 0.0
    vol_last_dir = None
    vol_last_t = 0.0
    prev_hand_mode = None
    last_unanimous = None
    first_stable = None
    toggle_notif = None
    toggle_notif_t = 0.0
    last_spoken = ""
    vol_activo = False
    api_update_t = 0.0
    album_art_url_cached = ""

    try:
        while True:
            frame = cam.read()
            if frame is None:
                print("Error leyendo cámara.")
                break

            t = time.time()
            timestamp_ms = int(t * 1000)
            accion = False

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = g.process(rgb, timestamp_ms)

            # ── Spotify API poll ──
            if api.ready and t - api_update_t > 1.0:
                api.update()
                api_update_t = t
                if api.album_art_url and api.album_art_url != album_art_url_cached:
                    album_art_url_cached = api.album_art_url
                    threading.Thread(
                        target=_download_album_art,
                        args=(api.album_art_url, api),
                        daemon=True,
                    ).start()

            # ── UI layers (draw below hand overlays) ──
            draw_top_bar(frame, voice.enabled, speech.enabled, True)
            draw_song_panel(frame, api, t)
            draw_album_art(frame, api)

            if result and result.hand_landmarks:
                now_frame = time.time()
                fist_count = 0
                open_count = 0
                index_count = 0
                peace_count = 0
                other_count = 0
                vol_activo = False

                for i in range(len(result.hand_landmarks)):
                    lm = result.hand_landmarks[i]
                    label = result.handedness[i][0].category_name
                    label = 'Right' if label == 'Left' else 'Left'

                    g._hand_last_seen[label] = now_frame
                    first_frame = label not in g._first_frame
                    g._first_frame[label] = True

                    g.draw_landmarks(frame, lm)
                    fc = g._finger_count(lm)
                    y = 48 + i * 24

                    sw = g.detectar_swipe(lm, t, label)
                    if sw and not accion:
                        if sw == 'R':
                            keys.next_track()
                            toggle_notif = "SIGUIENTE ▶▶"
                            toggle_notif_t = t
                            accion = True
                        elif sw == 'L':
                            keys.prev_track()
                            toggle_notif = "ANTERIOR ◀◀"
                            toggle_notif_t = t
                            accion = True

                    # ── Classify ──
                    if g.peace_sign(lm):
                        cl = 'peace'
                    elif g.solo_indice(lm):
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

                    estable = g._hand_class_cnt.get(label, 0) >= 2

                    # ── Gesture overlay text ──
                    gesture_text = ""
                    gesture_color = (200, 200, 200)
                    if g.peace_sign(lm):
                        gesture_text = "✌  LIKE"
                        gesture_color = (180, 100, 200)
                    elif g.mano_abierta(lm):
                        gesture_text = "✋  PLAY"
                        gesture_color = (80, 220, 50)
                    elif g.puno_play(lm):
                        gesture_text = "✊  PAUSA"
                        gesture_color = (60, 60, 230)
                    elif g.solo_indice(lm):
                        d = g.dir_indice(lm) or vol_last_dir
                        if d == 'UP':
                            gesture_text = "☝  SUBIR VOL"
                            gesture_color = (230, 170, 70)
                        elif d == 'DOWN':
                            gesture_text = "☝  BAJAR VOL"
                            gesture_color = (40, 200, 240)
                        else:
                            gesture_text = "☝  ÍNDICE"
                            gesture_color = (200, 200, 200)
                    draw_hand_info(frame, label, fc, gesture_text, 10, y, gesture_color)

                    # ── Actions ──
                    if not first_frame and estable:
                        if cl == 'index':
                            d = g.dir_indice(lm)
                            if d is None:
                                d = vol_last_dir
                            if d == 'UP' and t - vol_t > VOL_COOLDOWN:
                                keys.vol_up()
                                vol_t = t
                                vol_last_dir = 'UP'
                                vol_last_t = t
                            elif d == 'DOWN' and t - vol_t > VOL_COOLDOWN:
                                keys.vol_down()
                                vol_t = t
                                vol_last_dir = 'DOWN'
                                vol_last_t = t
                        elif cl == 'peace' and t - like_t > LIKE_COOLDOWN and not accion:
                            result_like = api.toggle_like()
                            if result_like is True:
                                toggle_notif = "❤ LIKE"
                                toggle_notif_t = t
                                accion = True
                                like_t = t
                            elif result_like is False:
                                toggle_notif = "💔 UNLIKE"
                                toggle_notif_t = t
                                accion = True
                                like_t = t
                        elif cl == 'fist':
                            fist_count += 1
                        elif cl == 'open':
                            open_count += 1
                    if cl == 'index':
                        vol_activo = True
                        if not first_frame and estable:
                            index_count += 1
                    elif cl == 'peace':
                        peace_count += 1
                    elif not first_frame and estable and cl == 'other':
                        other_count += 1

                # ── Play/Pause logic ──
                manos_claras = fist_count + open_count
                manos_ocupadas = index_count + peace_count + other_count

                if len(result.hand_landmarks) == 0:
                    cur_mode = 'none'
                elif manos_claras > 0 and manos_ocupadas == 0:
                    if fist_count > 0 and open_count == 0:
                        cur_mode = 'fist'
                    elif open_count > 0 and fist_count == 0:
                        cur_mode = 'open'
                    else:
                        cur_mode = 'mixed'
                else:
                    cur_mode = 'mixed'

                if first_stable is None and cur_mode not in ('none', 'mixed'):
                    first_stable = cur_mode
                    last_unanimous = cur_mode
                    prev_hand_mode = cur_mode
                    toggle_notif = 'GESTO REGISTRADO'
                    toggle_notif_t = t
                elif not accion and t - pp_t > PP_COOLDOWN and prev_hand_mode is not None:
                    def _should_play():
                        if api.ready:
                            return not api.is_playing
                        return True  # toggle always if no API

                    should_play = _should_play()
                    is_fist = cur_mode == 'fist' and prev_hand_mode not in ('fist', 'none', 'mixed')
                    is_open = cur_mode == 'open' and prev_hand_mode not in ('open', 'none', 'mixed')
                    is_fist_mixed = cur_mode == 'fist' and prev_hand_mode == 'mixed' and manos_ocupadas == 0 and last_unanimous != 'fist'
                    is_open_mixed = cur_mode == 'open' and prev_hand_mode == 'mixed' and manos_ocupadas == 0 and last_unanimous != 'open'

                    if is_fist or is_fist_mixed:
                        # fist = pausa → toggle only if playing
                        if not api.ready or api.is_playing:
                            keys.toggle_play()
                            pp_t = t
                            accion = True
                            toggle_notif = '⏸ PAUSA'
                            toggle_notif_t = t
                            last_unanimous = 'fist'
                    elif is_open or is_open_mixed:
                        # open = play → toggle only if paused
                        if not api.ready or not api.is_playing:
                            keys.toggle_play()
                            pp_t = t
                            accion = True
                            toggle_notif = '▶ PLAY'
                            toggle_notif_t = t
                            last_unanimous = 'open'

                if prev_hand_mode is None or cur_mode != prev_hand_mode:
                    prev_hand_mode = cur_mode

                stale = [h for h in g._first_frame if now_frame - g._hand_last_seen.get(h, 0) > 2]
                for h in stale:
                    del g._first_frame[h]
                    g._hand_class.pop(h, None)
                    g._hand_class_cnt.pop(h, None)

            # ── Voice commands ──
            try:
                while True:
                    cmd = cmd_queue.get_nowait()
                    if accion:
                        continue
                    if cmd in ("play", "reproducir", "tocar"):
                        keys.toggle_play()
                        toggle_notif = "▶ PLAY  (voz)"
                        toggle_notif_t = t
                    elif cmd in ("pause", "pausa", "parar", "stop"):
                        keys.toggle_play()
                        toggle_notif = "⏸ PAUSA  (voz)"
                        toggle_notif_t = t
                    elif cmd in ("like", "favorito", "me gusta", "favorite"):
                        r = api.toggle_like()
                        if r is True:
                            toggle_notif = "❤ LIKE  (voz)"
                        elif r is False:
                            toggle_notif = "💔 UNLIKE  (voz)"
                        toggle_notif_t = t
                    elif cmd in ("next", "siguiente", "proxima", "siguiente cancion"):
                        keys.next_track()
                        toggle_notif = "SIGUIENTE  (voz)"
                        toggle_notif_t = t
                    elif cmd in ("previous", "anterior", "volver", "cancion anterior"):
                        keys.prev_track()
                        toggle_notif = "ANTERIOR  (voz)"
                        toggle_notif_t = t
                    elif cmd in ("subir volumen", "volumen arriba", "mas alto"):
                        keys.vol_up()
                        toggle_notif = "SUBIR VOL  (voz)"
                        toggle_notif_t = t
                    elif cmd in ("bajar volumen", "volumen abajo", "mas bajo"):
                        keys.vol_down()
                        toggle_notif = "BAJAR VOL  (voz)"
                        toggle_notif_t = t
                    accion = True
            except queue.Empty:
                pass

            # ── Volume bar ──
            vol_pct = keys.get_vol_pct()
            draw_volume_bar(frame, vol_pct, vol_last_dir, vol_last_t, vol_activo, t)

            # ── Notification ──
            if toggle_notif:
                nc = _notif_color(toggle_notif)
                draw_notification(frame, toggle_notif, nc, t, toggle_notif_t, 1.0)
                if toggle_notif != last_spoken:
                    last_spoken = toggle_notif
                    # clean text for TTS
                    tts_text = toggle_notif.replace("▶", "").replace("⏸", "").replace("❤", "Like").replace("💔", "Unlike").replace("⏸", "Pausa").replace("▶", "Play").replace("✌", "Paz").replace("◀◀", "anterior").replace("▶▶", "siguiente").replace("SIGUIENTE", "Siguiente").replace("ANTERIOR", "Anterior").replace("GESTO REGISTRADO", "Gesto registrado")
                    voice.speak(tts_text.strip())
                if t - toggle_notif_t > 1.0:
                    toggle_notif = None

            cv2.imshow("Control por gestos - Spotify", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            elif key == ord('v') or key == ord('V'):
                voice.toggle()
            elif key == ord('s') or key == ord('S'):
                speech.toggle()

    except KeyboardInterrupt:
        pass
    finally:
        cam.release()
        cv2.destroyAllWindows()
        print("Programa terminado.")


if __name__ == "__main__":
    main()
