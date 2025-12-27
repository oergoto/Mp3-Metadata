import logging
import requests
import base64
import time
from typing import List, Optional, Dict, Any
from urllib.parse import quote

from mp3_autotagger.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from mp3_autotagger.core.models import Track
from mp3_autotagger.utils.normalization import remove_accents

logger = logging.getLogger(__name__)

class SpotifyClient:
    """
    Cliente para interactuar con la API de Spotify.
    Usa 'Client Credentials Flow' para buscar metadatos y audio features.
    """
    
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE_URL = "https://api.spotify.com/v1"

    def __init__(self):
        self.client_id = SPOTIFY_CLIENT_ID
        self.client_secret = SPOTIFY_CLIENT_SECRET
        self.access_token = None
        self.token_expiry = 0
        
        if not self.client_id or not self.client_secret:
            logger.warning("Spotify credentials not found (SPOTIFY_CLIENT_ID/SECRET).")

    def _get_token(self) -> Optional[str]:
        """Obtiene o renueva el access token."""
        if self.access_token and time.time() < self.token_expiry:
            return self.access_token

        if not self.client_id or not self.client_secret:
            return None

        try:
            auth_str = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {"grant_type": "client_credentials"}
            
            resp = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=10)
            if resp.status_code == 200:
                json_data = resp.json()
                self.access_token = json_data["access_token"]
                # Expires in usually 3600 seconds. Reserve 60s buffer.
                self.token_expiry = time.time() + json_data.get("expires_in", 3600) - 60
                return self.access_token
            else:
                logger.error(f"Spotify Auth Failed: {resp.status_code} {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Spotify Connection Error: {e}")
            return None

    def search_track(self, artist: str, title: str, limit: int = 5) -> List[Track]:
        """
        Busca tracks en Spotify.
        Retorna lista de objetos Track genéricos.
        """
        token = self._get_token()
        if not token:
            return []

        # Construir query más precisa: "artist:Name track:Title"
        # Limpiamos un poco para evitar errores de sintaxis en query
        clean_artist = artist.replace('"', '').replace("'", "")
        clean_title = title.replace('"', '').replace("'", "")
        
        # A veces la búsqueda específica falla si el nombre es muy diferente, probamos query general si falla?
        # Por ahora usaremos la query avanzada combinada.
        query = f"artist:{clean_artist} track:{clean_title}"
        
        # Fallback a búsqueda general si tiene caracteres raros o para maximizar recall
        # query = f"{clean_artist} {clean_title}"
        
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "q": query,
            "type": "track",
            "limit": limit
        }

        try:
            resp = requests.get(f"{self.API_BASE_URL}/search", headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"Spotify Search Error: {resp.status_code}")
                return []
            
            data = resp.json()
            items = data.get("tracks", {}).get("items", [])
            
            tracks = []
            for item in items:
                t = self._parse_track(item, artist, title)
                if t:
                    tracks.append(t)
            
            # Ordenar por score
            tracks.sort(key=lambda x: x.score, reverse=True)
            return tracks

        except Exception as e:
            logger.error(f"Spotify Search Exception: {e}")
            return []

    def search_broad(self, query: str, ref_artist: str = "", ref_title: str = "", limit: int = 5) -> List[Track]:
        """
        Búsqueda abierta en Spotify ("Hail Mary").
        Usa la query tal cual, sin filtros 'artist:' o 'track:'.
        Useful for remixes or messy filenames.
        """
        token = self._get_token()
        if not token:
            return []

        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "q": query,
            "type": "track",
            "limit": limit
        }

        try:
            resp = requests.get(f"{self.API_BASE_URL}/search", headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"Spotify Broad Search Error: {resp.status_code}")
                return []
            
            data = resp.json()
            items = data.get("tracks", {}).get("items", [])
            
            tracks = []
            for item in items:
                # Use ref_artist/ref_title for scoring validation
                t = self._parse_track(item, ref_artist, ref_title)
                if t:
                    tracks.append(t)
            
            # Ordenar por score
            tracks.sort(key=lambda x: x.score, reverse=True)
            return tracks

        except Exception as e:
            logger.error(f"Spotify Broad Search Exception: {e}")
            return []

    # get_audio_features REMOVED (Phase 17 - API Restriction)
    def _parse_track(self, item: Dict, search_artist: str, search_title: str) -> Optional[Track]:
        """Convierte JSON de Spotify a objeto Track."""
        try:
            s_name = item.get("name", "")
            s_artists = [a["name"] for a in item.get("artists", [])]
            s_artist_str = ", ".join(s_artists)
            
            album_obj = item.get("album", {})
            s_album = album_obj.get("name", "")
            s_date = album_obj.get("release_date", "") # YYYY-MM-DD or YYYY
            s_year = s_date[:4] if s_date else None
            
            # Cover Art (Largest)
            images = album_obj.get("images", [])
            cover_url = images[0]["url"] if images else None
            
            # ID y Popularidad
            s_id = item.get("id")
            # popularity = item.get("popularity", 0)
            
            # Score
            score = self._calculate_score(search_artist, search_title, s_artist_str, s_name)
            
            # Genre? Spotify NO DA géneros por Track, solo por Artista.
            # Podríamos buscar el género del artista principal si es crítico.
            # Por simplicidad, dejamos genre vacío por ahora o "Spotify".
            
            return Track(
                title=s_name,
                artist=s_artist_str,
                album=s_album,
                label=None, # Spotify Track object does NOT have label usually (Album might, check details)
                # Actually Full Album object has label, simplified one in search might not.
                genre=None, 
                year=s_year,
                cover_url=cover_url,
                duration_ms=item.get("duration_ms"),
                source="Spotify",
                score=score,
                id=s_id,
                url=item.get("external_urls", {}).get("spotify")
            )
        except Exception as e:
            logger.debug(f"Error parsing spotify item: {e}")
            return None

    def _calculate_score(self, s_artist: str, s_title: str, r_artist: str, r_title: str) -> float:
        import re
        
        # Normalización "Smart": Puntuación -> Espacios
        # Así 'we.amps' -> 'we amps' y coincide con 'we amps'
        def clean_tok(s: str) -> str:
            s = remove_accents(s.lower())
            s = re.sub(r"[^a-z0-9]", " ", s) # Todo lo que no sea letra/num -> espacio
            return s.strip()

        sa = clean_tok(s_artist)
        st = clean_tok(s_title)
        ra = clean_tok(r_artist)
        rt = clean_tok(r_title)
        
        # Jaccard sets
        def jaccard(a, b):
            set_a = set(a.split())
            set_b = set(b.split())
            if not set_a or not set_b: return 0.0
            
            inter = len(set_a.intersection(set_b))
            union = len(set_a.union(set_b))
            return inter / union if union > 0 else 0.0

        sim_art = jaccard(sa, ra)
        sim_tit = jaccard(st, rt)
        
        # Boost exact matches (substrings raw)
        # Check raw normalized without punctuation split
        # e.g. "we.amps" in "we.amps rules" -> true
        # But wait, we cleaned puctuation. "we amps" in "we amps rules". Yes.
        if sa and ra and (sa in ra or ra in sa): 
            sim_art = max(sim_art, 0.9)
        if st and rt and (st in rt or rt in st): 
            sim_tit = max(sim_tit, 0.9)
        
        if not sa:
            # FREE SEARCH MODE (Phase 22)
            # If search artist is empty, we assume search_title contains everything (Artist + Title)
            # Compare s_title against (r_artist + r_title)
            full_result = f"{ra} {rt}"
            score_normal = jaccard(st, full_result)
            
            # Boost if full substring match
            if st in full_result or full_result in st:
                score_normal = max(score_normal, 0.8)
                
            best_score = score_normal
            score_swapped = 0.0 # Define to avoid UnboundLocalError
        else:
            # Main Scoring (Normal)
            score_normal = (sim_art * 0.4) + (sim_tit * 0.6)
            
            # Swapped Scoring (Handling Title - Artist files)
            # Check Artist vs ResultTitle AND Title vs ResultArtist
            sim_art_swap = jaccard(sa, rt)
            sim_tit_swap = jaccard(st, ra)
            
            if sa and rt and (sa in rt or rt in sa): sim_art_swap = max(sim_art_swap, 0.9)
            if st and ra and (st in ra or ra in st): sim_tit_swap = max(sim_tit_swap, 0.9)
            
            score_swapped = (sim_art_swap * 0.4) + (sim_tit_swap * 0.6)
            
            best_score = max(score_normal, score_swapped)
            
        if best_score > 0.05:
            # Fix NameError (t -> r_artist/r_title)
            print(f"     [Scoring] '{r_artist} - {r_title}' | Normal={score_normal:.2f} Swap={score_swapped:.2f} Final={best_score:.2f}")

        return best_score
