from __future__ import annotations
import os
import requests

try:
    import requests_cache
    HAS_CACHE = True
except ImportError:
    HAS_CACHE = False

def get_cached_session(cache_name: str = "http_cache", expire_after_days: int = 7) -> requests.Session:
    """
    Retorna una sesión con caché SQLite si requests-cache está instalado.
    Si no, retorna una sesión normal de requests.
    
    Args:
        cache_name: Nombre del archivo de caché (sin extensión .sqlite).
        expire_after_days: Días de expiración del caché.
    """
    if HAS_CACHE:
        # Cache en el directorio actual o uno específico
        # Usaremos 'http_cache.sqlite' en el root del proyecto
        # backend='sqlite' es el default
        session = requests_cache.CachedSession(
            cache_name=cache_name,
            backend='sqlite',
            expire_after=expire_after_days * 86400, # segundos
            allowable_codes=[200, 404], # Cachear también "No encontrado" para no re-buscar
            match_headers=False,
            stale_if_error=True # Si falla la red, usar caché expirado
        )
        print(f"[Cache] Usando caché en '{cache_name}.sqlite'")
        return session
    else:
        print("[Cache] requests-cache no instalado. Usando sesión normal (sin caché).")
        return requests.Session()
