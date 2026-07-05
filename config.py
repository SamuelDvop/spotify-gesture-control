import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Camera
CAM_ID = 0
FRAME_W = 640
FRAME_H = 480

# Model path
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task"
)

# Virtual keys (Windows media keys)
VK_NEXT = 0xB0
VK_PREV = 0xB1
VK_PLAY = 0xB3

# Gesture thresholds
SWIPE_THR = 0.08
SWIPE_RESET = 0.03
DOUBLE_WIN = 1.2
PP_COOLDOWN = 0.8
LIKE_COOLDOWN = 2.0
VOL_COOLDOWN = 0.08
VOL_STEP = 0.04
FINGER_RATIO = 0.35
ORIENT_THR = 0.03

# UI Colors (BGR)
BG_DARK = (25, 20, 40)
BG_PANEL = (40, 35, 60)
BG_PANEL_TRANSPARENT = (60, 50, 80)
VIOLET = (200, 100, 150)
BLUE = (230, 170, 70)
YELLOW = (40, 200, 240)
GREEN = (80, 220, 50)
RED = (60, 60, 230)
PINK = (180, 100, 200)
TEXT_WHITE = (240, 240, 240)
TEXT_DIM = (160, 140, 180)
TEXT_GRAY = (120, 120, 120)
VOL_BAR_BG = (30, 30, 30)
VOL_BAR_BORDER = (50, 50, 50)

# Spotify API
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://localhost:8888/callback"
TOKEN_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "token_cache.json"
)

# category colors for note / song
CAT_COLORS = {
    "like": PINK,
    "dislike": RED,
}
