from __future__ import annotations

import os
from typing import Optional

from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TCON, COMM, APIC, WXXX, TPUB, TPE2, TPOS, TXXX, TBPM, ID3NoHeaderError, TCOP, TSRC, TPE4
from mutagen.mp3 import MP3, EasyMP3

from mp3_autotagger.data_structures.schemas import UnifiedTrackData, TXXXKeys


class Tagger:
    """
    Clase encargada de escribir los metadatos finales en el archivo MP3.
    Ahora consume UnifiedTrackData (Phase 13).
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def write_metadata(self, track_meta: UnifiedTrackData, cover_art_data: Optional[bytes] = None) -> bool:
        """
        Escribe los metadatos UnifiedTrackData en el archivo MP3.
        """
        path = track_meta.filepath_original
        if not os.path.exists(path):
            print(f"[Tagger] Error: Archivo no encontrado -> {path}")
            return False

        # Datos Consolidados
        title = track_meta.title
        artist = track_meta.artist_main
        album_artist = track_meta.album_artist
        album = track_meta.album
        year = track_meta.year
        genre = track_meta.genre_main
        track_num = track_meta.track_number
        disc_num = track_meta.disc_number
        
        # Cover Art: Usar el pasado explícitamente O el temporal adjunto al objeto (Hack Phase 13)
        if cover_art_data is None:
            if hasattr(track_meta, "temp_cover_bytes"):
                cover_art_data = track_meta.temp_cover_bytes
        
        # "Deep Inspection" Box Style requested by User
        print(f"\n╔══ [AUDITORÍA PROFUNDA] {os.path.basename(path)} ══╗")
        
        # 1. CORE ID3 (Lo básico)
        print(f"║ ► ID3v2.3 ESTÁNDAR")
        print(f"║   ├── Título:   {title}")
        print(f"║   ├── Artista:  {artist}")
        print(f"║   ├── Álbum:    {album}")
        print(f"║   ├── A.Artist: {album_artist}")
        print(f"║   ├── Año:      {year}")
        print(f"║   ├── Género:   {genre}")
        print(f"║   └── Track #:  {track_num}")

        # 2. DATOS EDITORIALES (El valor agregado)
        pub = track_meta.editorial.publisher or "MISSING ⚠️"
        cat = track_meta.editorial.catalog_number or "MISSING ⚠️"
        med = track_meta.editorial.media_format.value if track_meta.editorial.media_format else "Digital"
        sty = ", ".join(track_meta.editorial.styles) if track_meta.editorial.styles else "MISSING (Usando Genérico) ⚠️"
        
        print(f"║ ► DATOS EDITORIALES (Discogs/MB)")
        print(f"║   ├── Sello (TPUB):     {pub}")
        print(f"║   ├── Catálogo:         {cat}")
        print(f"║   ├── Formato:          {med}")
        print(f"║   ├── Estilos (Styles): {sty}")
        print(f"║   ├── Type / Status:    {track_meta.editorial.release_type.value} / {track_meta.editorial.release_status.value}")
        print(f"║   ├── Country:          {track_meta.editorial.country or '---'}")
        print(f"║   ├── ISRC:             {track_meta.ids.isrc or '---'}")
        print(f"║   ├── Remixer:          {track_meta.editorial.remixer or '---'}")
        print(f"║   ├── Mastered By:      {track_meta.editorial.credits_mastering or '---'}")

        # 3. TAGS PERSONALIZADOS (TXXX - La "Caja Fuerte")
        mb_rid = track_meta.ids.musicbrainz_release_id or '---'
        ds_rid = track_meta.ids.discogs_release_id or '---'
        sp_id = track_meta.ids.spotify_id or '---'
        source = track_meta.match_confidence
        
        print(f"║ ► TRAZABILIDAD (TXXX Tags)")
        print(f"║   ├── MB Release ID:    {mb_rid}")
        print(f"║   ├── Discogs Rel ID:   {ds_rid}")
        print(f"║   ├── Spotify ID:       {sp_id}")
        print(f"║   ├── Fuente:           {source} (Confianza)")
        
        # 4. AUDIO INTELLIGENCE REMOVED (Phase 17)
        print(f"╚══════════════════════════════════════════════════════╝\n")
        
        if self.dry_run:
            print("[Tagger] MODO DRY-RUN: No se realizaron cambios en el disco.")
            return True

        try:
            try:
                audio = ID3(path)
            except ID3NoHeaderError:
                audio = ID3()

            # --- ID3v2.3 Standard Tags ---
            if title: audio.add(TIT2(encoding=3, text=title))
            if artist: audio.add(TPE1(encoding=3, text=artist))
            if album: audio.add(TALB(encoding=3, text=album))
            if album_artist: audio.add(TPE2(encoding=3, text=album_artist))
            if year: audio.add(TDRC(encoding=3, text=year))
            if track_num: audio.add(TRCK(encoding=3, text=track_num))
            if disc_num: audio.add(TPOS(encoding=3, text=disc_num))
            if genre: audio.add(TCON(encoding=3, text=genre))
            
            # Phase 20: New Standard Tags
            if track_meta.editorial.copyright:
                from mutagen.id3 import TCOP
                audio.add(TCOP(encoding=3, text=track_meta.editorial.copyright))
            if track_meta.ids.isrc:
                 from mutagen.id3 import TSRC
                 audio.add(TSRC(encoding=3, text=track_meta.ids.isrc))
            if track_meta.editorial.remixer:
                 from mutagen.id3 import TPE4
                 audio.add(TPE4(encoding=3, text=track_meta.editorial.remixer))
            
            # Publisher
            if track_meta.editorial.publisher:
                audio.add(TPUB(encoding=3, text=track_meta.editorial.publisher))

            # --- TXXX Custom Tags (Unified Data Model) ---
            
            # Catalog Number
            if track_meta.editorial.catalog_number:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.CATALOG_NUMBER, text=track_meta.editorial.catalog_number))
            
            # Format (Renamed from Media Format)
            if track_meta.editorial.media_format:
                 text_val = track_meta.editorial.media_format.value if hasattr(track_meta.editorial.media_format, 'value') else str(track_meta.editorial.media_format)
                 audio.add(TXXX(encoding=3, desc=TXXXKeys.MEDIA_FORMAT, text=text_val))
                 
            # Release Type
            if track_meta.editorial.release_type:
                text_val = track_meta.editorial.release_type.value if hasattr(track_meta.editorial.release_type, 'value') else str(track_meta.editorial.release_type)
                audio.add(TXXX(encoding=3, desc=TXXXKeys.RELEASE_TYPE, text=text_val))

            # Release Status
            if track_meta.editorial.release_status:
                text_val = track_meta.editorial.release_status.value if hasattr(track_meta.editorial.release_status, 'value') else str(track_meta.editorial.release_status)
                audio.add(TXXX(encoding=3, desc=TXXXKeys.RELEASE_STATUS, text=text_val))

            # Country
            if track_meta.editorial.country:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.COUNTRY, text=track_meta.editorial.country))

            # Styles (List to String)
            if track_meta.editorial.styles:
                style_str = ", ".join(track_meta.editorial.styles)
                audio.add(TXXX(encoding=3, desc=TXXXKeys.STYLE, text=style_str))
                
            # Credits
            if track_meta.editorial.credits_mastering:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.MASTERED_BY, text=track_meta.editorial.credits_mastering))
            if track_meta.editorial.credits_mixing:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.MIXED_BY, text=track_meta.editorial.credits_mixing))

            # IDs
            if track_meta.ids.musicbrainz_track_id:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.MB_TRACK_ID, text=track_meta.ids.musicbrainz_track_id))
            if track_meta.ids.musicbrainz_release_id:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.MB_RELEASE_ID, text=track_meta.ids.musicbrainz_release_id))
            if track_meta.ids.discogs_release_id:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.DISCOGS_RELEASE_ID, text=str(track_meta.ids.discogs_release_id)))
            if track_meta.ids.spotify_id:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.SPOTIFY_ID, text=track_meta.ids.spotify_id))
            if track_meta.ids.acoustid_fingerprint:
                audio.add(TXXX(encoding=3, desc=TXXXKeys.ACOUSTID_ID, text=track_meta.ids.acoustid_fingerprint))

            # Comment (User Note)
            comment_text = track_meta.editorial.comment or 'Tagged by Mp3 Metadata Agent'
            audio.add(COMM(encoding=3, lang='eng', desc='Description', text=[comment_text]))

            # Web Link (WXXX)
            if track_meta.ids.discogs_release_id:
                url = f"https://www.discogs.com/release/{track_meta.ids.discogs_release_id}"
                audio.add(WXXX(encoding=3, desc='Discogs', url=url))
            
            if track_meta.ids.spotify_id:
                 url = f"https://open.spotify.com/track/{track_meta.ids.spotify_id}"
                 audio.add(WXXX(encoding=3, desc='Spotify', url=url))

            # Cover Art
            if cover_art_data:
                audio.add(
                    APIC(
                        encoding=3,
                        mime='image/jpeg', 
                        type=3, 
                        desc=u'Cover',
                        data=cover_art_data
                    )
                )

            audio.save(path, v2_version=3)
            print("[Tagger] Escritura exitosa.")
            return True

        except Exception as e:
            print(f"[Tagger] Error escribiendo tags: {e}")
            return False
