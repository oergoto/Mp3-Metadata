import requests
from typing import Optional

def download_image(url: str, timeout: int = 10) -> Optional[bytes]:
    """
    Descarga una imagen desde una URL y retorna sus bytes.
    Retorna None si falla.
    """
    if not url:
        return None
        
    try:
        # Usamos requests directo (sin cache persistente para imagenes, 
        # aunque requests-cache podría cachearlas si usamos una session cacheada)
        # Por ahora simple requests.get
        headers = {"User-Agent": "MP3-Metadata-Pipeline/1.0"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        
        ct = resp.headers.get("Content-Type", "")
        if "image" not in ct:
            print(f"[Image] Advertencia: Content-Type no es imagen ({ct}) para {url}")
            
        return resp.content
    except Exception as e:
        print(f"[Image] Error descargando imagen {url}: {e}")
        return None
