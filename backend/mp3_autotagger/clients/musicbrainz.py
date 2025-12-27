from __future__ import annotations

import os
import time
from typing import Optional, Dict, Any, List

import requests
from dotenv import load_dotenv

from mp3_autotagger.core.models import MBArtist, MBRelease, MBRecording


# ---------------------------------------------------------------------
# CARGAR VARIABLES DE ENTORNO
# ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

USER_AGENT = os.getenv(
    "USER_AGENT",
    "MP3-Metadata-Pipeline/1.0 (+contacto@omarempresa.com)"
)

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"


# ---------------------------------------------------------------------
# CLIENTE MUSICBRAINZ
# ---------------------------------------------------------------------
from mp3_autotagger.utils.cache import get_cached_session

# ---------------------------------------------------------------------
# CLIENTE MUSICBRAINZ
# ---------------------------------------------------------------------
class MusicBrainzClient:
    def __init__(self, user_agent: Optional[str] = None, min_delay: float = 1.0) -> None:
        # Configuración del encabezado obligatorio
        self.user_agent = user_agent or USER_AGENT
        self.min_delay = min_delay
        self._last_request_ts: float = 0.0
        
        # Inicializar sesión con caché
        self.session = get_cached_session(cache_name="mb_cache")

    # -------------------------
    # Throttling
    # -------------------------
    def _throttle(self) -> None:
        """
        Respeta el tiempo mínimo entre llamadas para cumplir buenas prácticas
        de MusicBrainz. Evita saturar el servicio.
        """
        now = time.time()
        elapsed = now - self._last_request_ts
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self._last_request_ts = time.time()

    # -------------------------
    # Método GET genérico
    # -------------------------
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{MUSICBRAINZ_BASE_URL}/{path}"
        headers = {"User-Agent": self.user_agent}

        if params is None:
            params = {}
        params.setdefault("fmt", "json")

        max_retries = 3
        backoff = 2

        for attempt in range(max_retries):
            self._throttle()
            try:
                # Usar la sesión con caché
                resp = self.session.get(url, headers=headers, params=params, timeout=30)
                
                # Debug: Saber si vino del caché
                if hasattr(resp, 'from_cache') and resp.from_cache:
                    pass

                resp.raise_for_status()
                return resp.json()
                
            except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as e:
                if attempt < max_retries - 1:
                    sleep_time = backoff * (attempt + 1)
                    print(f"  [MB] Advertencia: Error de conexión ({e}). Reintentando en {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    raise e
            except requests.HTTPError as e:
                # 503 is Service Unavailable (Rate Limit sometimes)
                if e.response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                     sleep_time = backoff * (attempt + 1)
                     print(f"  [MB] Advertencia: Error servidor {e.response.status_code}. Reintentando en {sleep_time}s...")
                     time.sleep(sleep_time)
                else:
                     raise e
        return {} # Should not reach here

    # -------------------------
    # Obtener información de RECORDING
    # -------------------------
    def get_recording(self, recording_id: str) -> Optional[MBRecording]:
        path = f"recording/{recording_id}"
        params = {"inc": "artists+releases+release-groups+tags+genres+isrcs+media"}

        try:
            data = self._get(path, params=params)
        except requests.RequestException as e:
            print(f"Error consultando MusicBrainz para recording_id={recording_id}: {e}")
            return None

        # Parseo del JSON hacia el modelo MBRecording
        title = data.get("title", "")
        # length viene en ms
        length = data.get("length")

        # Artistas
        artists_data = data.get("artist-credit") or []
        artists = []
        for credit in artists_data:
            artist_dict = credit.get("artist")
            if artist_dict:
                a_id = artist_dict.get("id")
                a_name = artist_dict.get("name")
                a_sort = artist_dict.get("sort-name")
                artists.append(MBArtist(id=a_id, name=a_name, sort_name=a_sort))

        # Releases
        releases_data = data.get("releases") or []
        releases = []
        for rel in releases_data:
            r_id = rel.get("id")
            r_title = rel.get("title")
            r_date = rel.get("date")  # "YYYY-MM-DD" o "YYYY"
            r_country = rel.get("country")
            r_status = rel.get("status")
            
            rg = rel.get("release-group") or {}
            rg_id = rg.get("id")
            rg_type = rg.get("primary-type")
            
            # Media Formats
            media_list = rel.get("media") or []
            formats = [m.get("format") for m in media_list if m.get("format")]

            releases.append(
                MBRelease(
                    id=r_id,
                    title=r_title,
                    date=r_date,
                    country=r_country,
                    status=r_status,
                    release_group_id=rg_id,
                    release_group_type=rg_type,
                    media_formats=formats
                )
            )

        # Parse tags/genres
        tag_list = []
        raw_tags = data.get("tags") or []
        raw_genres = data.get("genres") or []
        
        # Merge lists (MB separates them in recent versions)
        all_tags = raw_tags + raw_genres
        # Sort by count desc if available (higher count = more relevant)
        all_tags.sort(key=lambda x: x.get("count", 0), reverse=True)
        
        seen_tags = set()
        for t in all_tags:
            name = t.get("name")
            if name and name not in seen_tags:
                tag_list.append(name.title()) # Capitalize like "House", "Techno"
                seen_tags.add(name)
        
        return MBRecording(
            id=data.get("id"),
            title=title,
            length=length,
            artists=artists,
            releases=releases,
            tags=tag_list,
            isrcs=data.get("isrcs") or []
        )
