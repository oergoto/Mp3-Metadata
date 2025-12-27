from dotenv import load_dotenv
import os

# Cargar variables desde .env en la raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
ACOUSTID_API_KEY = os.getenv("ACOUSTID_API_KEY")
MB_USER_TOKEN = os.getenv("MB_USER_TOKEN")
USER_AGENT = os.getenv("USER_AGENT", "MP3-Metadata-Pipeline/1.0 (+contacto@example.com)")

if not ACOUSTID_API_KEY:
    raise RuntimeError("ACOUSTID_API_KEY no está configurada en .env")

# ------------------------------------------------------
# HEURISTICS & THRESHOLDS (Centralized)
# ------------------------------------------------------
COMPILATION_KEYWORDS = [
    "best of", "greatest hits", "the very best", "dance anthems",
    "hits of", "mega hits", "collection", "collections", 
    "anthology", "various artists"
]

CONFIDENCE_THRESHOLD_HIGH = 0.90
CONFIDENCE_THRESHOLD_MEDIUM = 0.70