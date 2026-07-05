import cv2
from config import (
    VIOLET, BLUE, YELLOW, GREEN, RED, PINK,
    TEXT_WHITE, TEXT_DIM, TEXT_GRAY,
    BG_PANEL,
    VOL_BAR_BG, VOL_BAR_BORDER,
)


def _put_text(img, text, pos, color=TEXT_WHITE, scale=0.5, thick=1, font=cv2.FONT_HERSHEY_DUPLEX):
    cv2.putText(img, text, pos, font, scale, (0, 0, 0), thick + 1, cv2.LINE_AA)
    cv2.putText(img, text, pos, font, scale, color, thick, cv2.LINE_AA)


def _panel_bg(img, x1, y1, x2, y2, alpha=0.5):
    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), BG_PANEL, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)


def draw_hand_info(frame, label, fc, gesture_text, x, y, color=VIOLET):
    if gesture_text:
        _put_text(frame, gesture_text, (x, y), color, 0.5, 2)


def draw_notification(frame, text, color, t_now, t_event, duration=1.0):
    if t_event is None:
        return
    alpha = max(0, 1 - (t_now - t_event) / duration)
    if alpha <= 0:
        return
    h, w = frame.shape[:2]
    x = (w - len(text) * 14) // 2
    _put_text(frame, text, (x, h // 2 - 60),
              color, 0.6, max(2, int(alpha * 4)))


def draw_volume_bar(frame, vol_pct, vol_last_dir, vol_last_t, vol_activo, t):
    h, w = frame.shape[:2]
    bar_w = 260
    bar_h = 18
    bar_x = (w - bar_w) // 2
    bar_y = h - 35
    fill = int(bar_w * vol_pct / 100)

    if vol_pct < 30:
        vol_color = GREEN
    elif vol_pct < 60:
        vol_color = BLUE
    elif vol_pct < 85:
        vol_color = YELLOW
    else:
        vol_color = RED

    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), VOL_BAR_BG, -1)
    if fill > 4:
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), vol_color, -1)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), VOL_BAR_BORDER, 1)
    _put_text(frame, f"VOL  {vol_pct}%", (bar_x + 8, bar_y + 13), TEXT_WHITE, 0.4, 1)


def draw_song_panel(frame, spotify_api, t):
    h, w = frame.shape[:2]
    panel_x = 10
    panel_y = h - 90
    panel_w = 220
    panel_h = 50

    if not spotify_api or not spotify_api.ready or not spotify_api.track_name:
        _panel_bg(frame, panel_x, panel_y, panel_x + panel_w, panel_y + panel_h, 0.4)
        _put_text(frame, "♫ Sin reproducción", (panel_x + 10, panel_y + 20), TEXT_DIM, 0.4, 1)
        return

    track = spotify_api.track_name
    artist = spotify_api.track_artist
    progress = spotify_api.progress_ms
    duration = spotify_api.duration_ms
    liked = spotify_api.liked

    _panel_bg(frame, panel_x, panel_y, panel_x + panel_w, panel_y + panel_h, 0.4)

    heart = "❤" if liked else "♡"
    hc = RED if liked else TEXT_DIM
    _put_text(frame, heart, (panel_x + 6, panel_y + 17), hc, 0.45, 2)

    max_c = 24
    dt = track if len(track) <= max_c else track[:max_c - 2] + ".."
    _put_text(frame, dt, (panel_x + 22, panel_y + 17), TEXT_WHITE, 0.4, 1)

    da = artist if len(artist) <= max_c else artist[:max_c - 2] + ".."
    _put_text(frame, da, (panel_x + 22, panel_y + 33), TEXT_DIM, 0.35, 1)

    if duration > 0:
        pb_y = panel_y + panel_h - 4
        pb_w = panel_w - 12
        pb_fill = int(pb_w * progress / duration)
        cv2.rectangle(frame, (panel_x + 6, pb_y), (panel_x + 6 + pb_w, pb_y + 3), VOL_BAR_BG, -1)
        if pb_fill > 2:
            cv2.rectangle(frame, (panel_x + 6, pb_y), (panel_x + 6 + pb_fill, pb_y + 3), VIOLET, -1)


def draw_album_art(frame, spotify_api):
    if not spotify_api or spotify_api.album_art is None:
        return
    img = spotify_api.album_art
    if img is None:
        return
    h, w = frame.shape[:2]
    s = 60
    x = w - s - 10
    y = h - s - 40

    try:
        art = cv2.resize(img, (s, s))
        cv2.rectangle(frame, (x - 1, y - 1), (x + s + 1, y + s + 1), BG_PANEL, -1)
        cv2.rectangle(frame, (x - 1, y - 1), (x + s + 1, y + s + 1), VIOLET, 1)
        frame[y:y + s, x:x + s] = art
    except:
        pass


def draw_top_bar(frame, voice_on=True, speech_on=False, speech_avail=False):
    h, w = frame.shape[:2]
    _put_text(frame, "ESC Salir", (10, 22), TEXT_DIM, 0.35, 1)
    x = w - 30
    if speech_avail:
        s_text = "🎤" if speech_on else "🎤"
        s_color = GREEN if speech_on else TEXT_DIM
        _put_text(frame, s_text, (x - 60, 22), s_color, 0.35, 1)
        _put_text(frame, "[S]", (x - 105, 22), TEXT_DIM, 0.28, 1)
    v_text = "🔊" if voice_on else "🔇"
    v_color = GREEN if voice_on else TEXT_DIM
    _put_text(frame, v_text, (x - 10, 22), v_color, 0.35, 1)
    _put_text(frame, "[V]", (x - 40, 22), TEXT_DIM, 0.28, 1)
