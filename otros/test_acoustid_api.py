import os
import json

import acoustid
import requests
from dotenv import load_dotenv

# Cargar .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

ACOUSTID_API_KEY = os.getenv("ACOUSTID_API_KEY")

if not ACOUSTID_API_KEY:
    raise RuntimeError("ACOUSTID_API_KEY no está configurada en .env")

# Ruta de prueba (coge uno de los que ya probaste)
TEST_FILE = "/Users/omarem4/Mi unidad (oergoto@gmail.com)/PROYECTOS/Mp3 Metadata Music Library/Music-Library-RAW/01. F.R.E.A.K (Original Mix).mp3"

print("Usando archivo:", TEST_FILE)
print("API Key:", ACOUSTID_API_KEY)

# 1) Obtener fingerprint y duración
duration, fp = acoustid.fingerprint_file(TEST_FILE)

# Asegurarnos de que duration es entero
duration_int = int(round(duration))

# Asegurarnos de que el fingerprint es string (no bytes)
if isinstance(fp, bytes):
    fp_str = fp.decode("ascii")
else:
    fp_str = fp

print("Duración (float):", duration)
print("Duración (int):", duration_int)
print("Fingerprint (primeros 80 chars):", fp_str[:80], "...")

# 2) Llamar a la API de AcoustID directamente
url = "https://api.acoustid.org/v2/lookup"
params = {
    "client": ACOUSTID_API_KEY,
    "duration": duration_int,   # OBLIGATORIO entero
    "fingerprint": fp_str,      # string normal
    "meta": "recordings+releasegroups+releases+tracks+compress",
}

resp = requests.get(url, params=params, timeout=30)
print("Status HTTP:", resp.status_code)

data = resp.json()
print("Respuesta cruda de AcoustID:")
print(json.dumps(data, indent=2, ensure_ascii=False))