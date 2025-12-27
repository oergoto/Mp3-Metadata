from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from mp3_autotagger.config import DISCOGS_TOKEN, USER_AGENT


class DiscogsClientError(Exception):
    """Error genérico del cliente Discogs."""
    pass


from mp3_autotagger.utils.cache import get_cached_session

@dataclass
class DiscogsClient:
    """
    Cliente mínimo para la API de Discogs, usando autenticación por token.

    - Respeta un delay mínimo entre requests (min_delay).
    - Envuelve errores de red y HTTP en DiscogsClientError.
    """
    base_url: str = "https://api.discogs.com"
    token: Optional[str] = DISCOGS_TOKEN
    user_agent: str = USER_AGENT
    min_delay: float = 1.0  # segundos entre requests para ser amable con la API

    def __post_init__(self) -> None:
        if not self.token:
            raise RuntimeError("DISCOGS_TOKEN no está configurado en .env / config.")

        # Usar caché separado para Discogs
        self.session = get_cached_session(cache_name="discogs_cache")
        
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Authorization": f"Discogs token={self.token}",
            }
        )
        self._last_request_time = 0.0
        self._lock = threading.Lock()

        # Mensaje de verificación rápida
        print("DiscogsClient inicializado correctamente.")
        print(f"User-Agent: {self.user_agent}")

    # --------------------------------------------------------
    # Utilidades internas
    # --------------------------------------------------------

    def _sleep_if_needed(self) -> None:
        """Respeta min_delay entre llamadas para no saturar la API. Debe llamarse bajo lock."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Envuelve requests.request con:
        - THREAD SAFETY (Lock)
        - loop infinito de reintento en 429 (Rate Limit).
        - espera forzosa de 65s en 429.
        - espera preventiva de 1.1s tras éxito.
        """
        url = f"{self.base_url}{path}"
        
        # Bucle infinito de intentos (Ticket Crítico: Paciencia del Robot)
        while True:
            with self._lock:
                self._sleep_if_needed()
                
                try:
                    resp = self.session.request(
                        method=method.upper(),
                        url=url,
                        params=params,
                        timeout=20,
                    )
                    
                    # Actualizamos tiempo de request
                    self._last_request_time = time.time()
                    
                    # 1. Manejo explícito de 429 (Too Many Requests) - ZONA DE ESPERA
                    # Forzamos conversión a int por si alguna librería intermedia (cache?) lo devuelve como str
                    try:
                        code = int(resp.status_code)
                    except:
                        code = 0
                    
                    if code == 429:
                        print(f"[ALERTA] Límite de API alcanzado (429) en {url}.")
                        print("[ALERTA] El sistema está durmiendo 65 segundos... Zzz...")
                        
                        # ANTI-CACHE: Si estamos usando cache y recibimos 429, BORRAR esa entrada
                        # para evitar leer el 429 del cache en el siguiente loop.
                        if hasattr(self.session, 'cache'):
                            try:
                                self.session.cache.delete_url(url)
                                print("[Internal] Entrada de caché 429 invalidada.")
                            except Exception:
                                pass

                        # Pausa absoluta del hilo por 65s
                        time.sleep(65.0)
                        
                        # Reintentar inmediatamente loop
                        continue
                    
                    # 2. Manejo de 404 (Not Found) -> None
                    if resp.status_code == 404:
                        return None
                    
                    # 3. Otros errores HTTP (500, 401, etc)
                    if resp.status_code >= 400:
                        text_preview = resp.text[:300]
                        raise DiscogsClientError(
                            f"Discogs devolvió error HTTP {resp.status_code}: {text_preview}"
                        )
                        
                    # 4. Éxito (200 OK)
                    # Pausa preventiva para no saturar
                    time.sleep(1.1)
                    
                    # 5. Rate Limit Proactivo (Optimización "Smart Robot")
                    # Leemos los headers para saber cuánto nos queda antes del bloqueo
                    try:
                        remaining = int(resp.headers.get("X-Discogs-Ratelimit-Remaining", 60))
                        if remaining < 2:
                            print(f"[Discogs] Rate Limit Buffer bajo ({remaining}). Pausa preventiva de 5s...")
                            time.sleep(5.0)
                    except Exception:
                        pass
                    
                    try:
                        return resp.json()
                    except ValueError as e:
                         # Si el contenido no es json válido
                        raise DiscogsClientError(f"Respuesta JSON inválida desde Discogs ({url}).") from e

                except requests.exceptions.ReadTimeout as e:
                    raise DiscogsClientError(f"Timeout al llamar a Discogs ({url}): {e}") from e
                except requests.RequestException as e:
                    raise DiscogsClientError(f"Error de red al llamar a Discogs ({url}): {e}") from e

    # --------------------------------------------------------
    # Métodos públicos específicos
    # --------------------------------------------------------

    def search_releases(
        self,
        query: Optional[str] = None,
        artist: Optional[str] = None,
        release_title: Optional[str] = None,
        track_title: Optional[str] = None,
        year: Optional[int] = None,
        per_page: int = 10,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Envuelve el endpoint oficial:
        GET /database/search
        """
        params: Dict[str, Any] = {
            "type": "release",
            "per_page": per_page,
            "page": page,
        }

        if query:
            params["q"] = query
        if artist:
            params["artist"] = artist
        if release_title:
            params["release_title"] = release_title
        if track_title:
            params["track"] = track_title
        if year:
            params["year"] = year

        resp = self._request("GET", "/database/search", params=params)
        
        # Si devuelve None (404), retornamos estructura vacía para no romper clientes
        if resp is None:
            return {"results": [], "pagination": {}}
            
        return resp

    def get_release(self, release_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene el detalle de un release específico.
        
        Retorna None si no existe (404).
        """
        path = f"/releases/{release_id}"
        return self._request("GET", path)
