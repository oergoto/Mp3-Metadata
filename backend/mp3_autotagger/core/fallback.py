
import os
import re
from typing import Optional, Dict, List, Any
from mutagen import File as MutagenFile
from mp3_autotagger.clients.discogs import DiscogsClient, DiscogsClientError
from mp3_autotagger.core.matching import _jaccard_similarity

def clean_filename(filename: str) -> str:
    """
    Limpia un nombre de archivo para maximizar la probabilidad de encontrar
    artista y título. Quita extensiones, numeraciones, calidad (320kbps), etc.
    """
    # 1. Quitar extensión
    name = os.path.splitext(filename)[0]
    
    # 2. Quitar patrones comunes de "ruido"
    name = re.sub(r"^\d+[\.\-]\s*", "", name) # "01. "
    name = re.sub(r"^\d+[A-Z]?\s-\s\d+\s-\s", "", name) # "1A - 128 - "
    name = re.sub(r"^y2mate\.com\s-\s", "", name, flags=re.IGNORECASE)
    
    # Quitar info técnica al final
    name = re.sub(r"_320kbps", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(320\s?kbps\)", "", name, flags=re.IGNORECASE)
    
    # 3. Reemplazar guiones bajos y puntos por espacios
    name = re.sub(r"[_\.]", " ", name)
    
    # 4. Quitar espacios múltiples
    name = re.sub(r"\s+", " ", name).strip()
    
    return name

def clean_title_aggressive(title: str) -> str:
    """Quita remix, mix, feat, parentesis, etc para busqueda agnostica."""
    t = re.sub(r"\(.*?\)", "", title)
    t = re.sub(r"\[.*?\]", "", t)
    t = re.sub(r"\b(original|extended|club|remix|mix|edit|vocal|dub|feat|ft|featuring)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def get_audio_duration(file_path: str) -> Optional[float]:
    """Obtiene la duración en segundos del archivo usando mutagen."""
    try:
        audio = MutagenFile(file_path)
        if audio and audio.info and audio.info.length:
            return audio.info.length
    except Exception:
        pass
    return None

def fallback_search_by_filename(
    file_path: str,
    discogs_client: DiscogsClient
) -> Optional[Dict[str, Any]]:
    """
    Intenta identificación avanzada por nombre en Discogs.
    Estrategia simplificada: Búsqueda por nombre de archivo limpio (ignorando Key/BPM si existian).
    """
    
    filename = os.path.basename(file_path)
    duration = get_audio_duration(file_path)
    
    if not duration:
        print(f"[Fallback] No se pudo leer duración de: {filename}")
        return None

    clean_query = clean_filename(filename)
    print(f"[Fallback] Buscando por texto: '{clean_query}'")

    # Estrategia de búsqueda: [Query Exacta, Query Relajada]
    # Calculamos relaxed_query
    relaxed_query = re.sub(r"\((.*?)\)", "", clean_query) # Quitar parentesis
    relaxed_query = re.sub(r"\[.*?\]", "", relaxed_query) # Quitar corchetes
    relaxed_query = re.sub(r"\b(original|extended|club|remix|mix|edit|vocal|dub|feat|ft|featuring|presents|pres)\b", "", relaxed_query, flags=re.IGNORECASE)
    relaxed_query = re.sub(r"\s+", " ", relaxed_query).strip()
    
    queries_to_try = [clean_query]
    if len(relaxed_query) > 3 and relaxed_query != clean_query:
        queries_to_try.append(relaxed_query)

    for query in queries_to_try:
        is_relaxed = (query == relaxed_query and query != clean_query)
        label = "RELAJADA" if is_relaxed else "EXACTA"
        if is_relaxed:
             print(f"[Fallback] Re-intentando ({label}): '{query}'")
        else:
             print(f"[Fallback] Buscando ({label}): '{query}' (Duración: {duration:.1f}s)")

        try:
            data = discogs_client.search_releases(
                query=query,
                page=1,
                per_page=10
            )
            
            results = data.get("results") or []
            
            for cand in results:
                if cand.get("type") != "release":
                    continue
                    
                cand_title = cand.get("title", "")
                
                # Jaccard para validar titulo
                # bajamos umbral a 0.15 para capturar matches difícles (ej. "Artist - Title" vs "Title")
                threshold = 0.15 if is_relaxed else 0.25
                sim = _jaccard_similarity(query, cand_title)
                
                if sim < threshold: 
                    continue
                    
                cand_id = cand.get("id")
                
                # Obtener detalles para duración
                release_details = discogs_client.get_release(cand_id)
                if not release_details:
                    continue
                    
                tracklist = release_details.get("tracklist") or []
                
                for trk in tracklist:
                    dur_str = trk.get("duration", "")
                    if not dur_str:
                        continue
                    
                    try:
                        parts = dur_str.split(":")
                        if len(parts) == 2:
                            cand_dur = int(parts[0]) * 60 + int(parts[1])
                        elif len(parts) == 3: # H:M:S
                             cand_dur = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                            
                        # Tolerancia 5s
                        diff = abs(cand_dur - duration)
                        
                        if diff <= 5.0:
                            print(f"  -> MATCH FALLBACK: {cand_title} // Track: {trk.get('title')} ({dur_str})")
                            
                            return {
                                "fallback_source": "discogs_filename",
                                "discogs_id": cand_id,
                                "discogs_title": trk.get("title"),
                                "discogs_artist": release_details.get("artists_sort") or cand.get("artist"),
                                "discogs_album": release_details.get("title"),
                                "discogs_year": release_details.get("year"),
                                "discogs_genre": release_details.get("genres"),
                                "discogs_styles": release_details.get("styles"),
                                "discogs_cover": cand.get("cover_image") or cand.get("thumb"),
                                "discogs_format": cand.get("format"),
                                "discogs_label": (release_details.get("labels") or [{}])[0].get("name"),
                                "discogs_country": release_details.get("country"),
                                "discogs_release_url": release_details.get("uri"),
                            }
                    except Exception:
                        continue
        except DiscogsClientError as e:
            print(f"[Fallback] Error Discogs API: {e}")
            break
            
    return None
