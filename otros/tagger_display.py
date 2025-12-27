from typing import Dict, List
import logging

# Asumiendo que recibimos el objeto UnifiedTrackData (track_data)

def print_deep_inspection(track_data):
    """
    Imprime una auditoría forense de los metadatos que SE VAN A ESCRIBIR.
    Revela si realmente estamos cumpliendo la promesa de las 20 etiquetas.
    """
    print(f"\n╔══ [AUDITORÍA PROFUNDA] {track_data.filename_new} ══╗")
    
    # 1. CORE ID3 (Lo básico)
    print(f"║ ► ID3v2.3 ESTÁNDAR")
    print(f"║   ├── Título:   {track_data.title}")
    print(f"║   ├── Artista:  {track_data.artist_main}")
    print(f"║   ├── Álbum:    {track_data.album}")
    print(f"║   ├── A.Artist: {track_data.album_artist}")
    print(f"║   ├── Año:      {track_data.year}")
    print(f"║   ├── Género:   {track_data.genre_main}")
    print(f"║   └── Track #:  {track_data.track_number}")

    # 2. DATOS EDITORIALES (El valor agregado)
    print(f"║ ► DATOS EDITORIALES (Discogs/MB)")
    print(f"║   ├── Sello (TPUB):     {track_data.editorial.publisher or 'MISSING '}")
    print(f"║   ├── Catálogo:         {track_data.editorial.catalog_number or 'MISSING '}")
    print(f"║   ├── Formato:          {track_data.editorial.media_format or 'Digital'}")
    print(f"║   └── Estilos (Styles): {', '.join(track_data.editorial.styles) if track_data.editorial.styles else 'MISSING (Usando Genérico) '}")

    # 3. TAGS PERSONALIZADOS (TXXX - La "Caja Fuerte")
    print(f"║ ► TRAZABILIDAD (TXXX Tags)")
    print(f"║   ├── MB Release ID:    {track_data.ids.musicbrainz_release_id or '---'}")
    print(f"║   ├── Discogs Rel ID:   {track_data.ids.discogs_release_id or '---'}")
    print(f"║   ├── Spotify ID:       {track_data.ids.spotify_id or '---'}")
    print(f"║   ├── Fuente:           {track_data.match_confidence} (Confianza)")
    
    # 4. AUDIO INTELLIGENCE (Spotify Features)
    print(f"║ ► AUDIO INTELLIGENCE")
    print(f"║   ├── Energy:       {track_data.audio.energy}")
    print(f"║   ├── Danceability: {track_data.audio.danceability}")
    print(f"║   └── Valence:      {track_data.audio.valence}")
    print(f"╚══════════════════════════════════════════════════════╝\n")