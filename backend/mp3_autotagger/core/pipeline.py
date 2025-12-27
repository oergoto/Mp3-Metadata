from __future__ import annotations
import logging

from dataclasses import dataclass
from typing import Optional, Dict, Any
import os
import re

from mp3_autotagger.data_structures.schemas import UnifiedTrackData, ExternalIDs, EditorialMetadata, AudioFeatures
from mp3_autotagger.config import CONFIDENCE_THRESHOLD_HIGH
from mp3_autotagger.core.mappers import MusicBrainzMapper, DiscogsMapper
from mp3_autotagger.services.identity import IdentityService
from mp3_autotagger.services.enrichment import EnrichmentService
from mp3_autotagger.core.acoustid import analyze_file, identify_with_acoustid
from mp3_autotagger.core.selection import select_best_acoustid_candidate
from mp3_autotagger.core.fallback import fallback_search_by_filename, clean_filename, clean_title_aggressive
from mp3_autotagger.clients.musicbrainz import MusicBrainzClient
from mp3_autotagger.clients.spotify import SpotifyClient
from mp3_autotagger.core.models import MBRecording, MBArtist, MBRelease
from mp3_autotagger.clients.discogs import DiscogsClient
from mp3_autotagger.core.matching import match_track_mb_to_discogs, DiscogsMatchResult, _jaccard_similarity
from mp3_autotagger.utils.images import download_image
from mp3_autotagger.utils.normalization import remove_accents
from mp3_autotagger.utils.cleaner import FilenameCleaner

@dataclass
class ProcessingResult:
    """
    Resultado final del procesamiento de un archivo.
    Contiene la metadata consolidada y el estado de la identificación.
    """
    file_path: str
    track_metadata: UnifiedTrackData
    discogs_result: Optional[DiscogsMatchResult] = None
    spotify_used: bool = False
    
    def get_display_title(self) -> str:
        return self.track_metadata.title or "Unknown Title"

    def get_display_artist(self) -> str:
        return self.track_metadata.artist_main or "Unknown Artist"

class PipelineCore:
    def __init__(self, use_discogs: bool = True, use_spotify: bool = True):
        self.logger = logging.getLogger(__name__)
        self.mb_client = MusicBrainzClient()
        self.use_discogs = use_discogs
        self.use_spotify = use_spotify
        self.discogs_client = DiscogsClient() if use_discogs else None
        self.spotify_client = SpotifyClient() if use_spotify else None

        # Pipeline 2.0 Services
        self.identity_service = IdentityService(self.spotify_client, self.mb_client)
        self.enrichment_service = EnrichmentService(self.discogs_client, self.spotify_client)

    def process_file(self, file_path: str) -> ProcessingResult:
        """
        Ejecuta el pipeline completo para un archivo:
        1. Análisis local (Mutagen)
        2. AcoustID
        3. MusicBrainz
        4. Spotify (Fallback & Enrich)
        5. Discogs (Linked/Fallback)
        """
        # 1. Análisis y AcoustID
        base_info = analyze_file(file_path)
        candidates = identify_with_acoustid(file_path)
        best_cand = select_best_acoustid_candidate(
            candidates, 
            original_tags=base_info["tags"], 
            filename=os.path.basename(file_path)
        )
        
        # 2. MusicBrainz (via Mapper)
        mb_rec = None
        
        if best_cand:
            acoustid_rec_id = best_cand["recording_id"]
            mb_rec = self.mb_client.get_recording(acoustid_rec_id)

        # INIT UNIFIED TRACK DATA
        if mb_rec:
            # Create from MusicBrainz
            track_meta = MusicBrainzMapper.map(mb_rec, file_path)
            if best_cand:
                track_meta.ids.acoustid_fingerprint = best_cand.get("recording_id")
        else:
            # Create Empty / Local
            track_meta = UnifiedTrackData(
                title=base_info["tags"].get("title", [os.path.basename(file_path)])[0] if base_info["tags"].get("title") else os.path.basename(file_path),
                artist_main=base_info["tags"].get("artist", ["Unknown Artist"])[0] if base_info["tags"].get("artist") else "Unknown Artist",
                album=base_info["tags"].get("album", [""])[0] if base_info["tags"].get("album") else "",
                album_artist=base_info["tags"].get("albumartist", [""])[0] if base_info["tags"].get("albumartist") else "",
                genre_main=base_info["tags"].get("genre", [""])[0] if base_info["tags"].get("genre") else "",
                track_number=base_info["tags"].get("tracknumber", [""])[0] if base_info["tags"].get("tracknumber") else "",
                disc_number=base_info["tags"].get("discnumber", [""])[0] if base_info["tags"].get("discnumber") else "",
                year=base_info["tags"].get("date", [""])[0] if base_info["tags"].get("date") else "",
                filepath_original=file_path
            )
        
        # 4. Spotify Integration (Enrichment Or Fallback)
        spotify_used = False
        
        # Decide search query from Unified Data
        search_artist = track_meta.artist_main
        search_title = track_meta.title
        
        # If unknown, try simplified filename parsing
        if not search_artist or search_artist == "Unknown Artist":
             clean_name_for_search = clean_filename(os.path.basename(file_path))
             if " - " in clean_name_for_search:
                 parts = clean_name_for_search.split(" - ", 1)
                 search_artist = parts[0].strip()
                 search_title = parts[1].strip()
             else:
                 search_title = clean_name_for_search
             
        if self.use_spotify and self.spotify_client and search_artist and search_title:
            s_tracks = self.spotify_client.search_track(search_artist, search_title)
            if s_tracks:
                best_spot = s_tracks[0]
                
                # ---------------------------------------------------------
                # STRICT RULE: Match Confidence > 90%
                # ---------------------------------------------------------
                if best_spot.score < CONFIDENCE_THRESHOLD_HIGH: # 0.90
                    self.logger.warning(f"[Strict] Match descartado por baja confianza ({best_spot.score:.2f} < {CONFIDENCE_THRESHOLD_HIGH})")
                    best_spot = None
                    spotify_used = False
                
                # ---------------------------------------------------------
                # STRICT RULE: Duration Tolerance +/- 5s
                # ---------------------------------------------------------
                elif best_spot.duration_ms:
                    local_dur = base_info.get("duration")
                    match_dur_sec = best_spot.duration_ms / 1000.0
                    
                    if local_dur:
                        diff = abs(local_dur - match_dur_sec)
                        if diff > 5.0:
                            self.logger.warning(f"[Strict] Match descartado por duración: Local={local_dur:.1f}s vs Match={match_dur_sec:.1f}s (Diff={diff:.1f}s)")
                            best_spot = None
                            spotify_used = False

                if best_spot:
                    self.logger.info(f"Spotify Match: {best_spot.title} ({best_spot.artist}) [Score={best_spot.score:.2f}]")
                    spotify_used = True
                    
                    # FORCE Overwrite of Title/Artist to clean data (User Rule: "Never leave filename")
                    track_meta.title = best_spot.title
                    track_meta.artist_main = best_spot.artist
                    
                    if not track_meta.album or track_meta.album == "Unknown Album":
                        track_meta.album = best_spot.album
                    if not track_meta.year and best_spot.year:
                        track_meta.year = best_spot.year
                        track_meta.editorial.release_date = best_spot.year
    
                    # Spotify Specifics
                    # Spotify Specifics
                    track_meta.ids.spotify_id = best_spot.id
                    track_meta.ids.spotify_url = best_spot.url # Phase 24
                    track_meta.audio.duration_ms = best_spot.duration_ms
                    track_meta.match_confidence = best_spot.score
                    
                    # Audio Intelligence (REMOVED per User Rule: No BPM/Key)
                    # pass
                
        # 3. Discogs (Standard Matching & Fallback)
        discogs_res = None
        fallback_res = None

        if self.use_discogs:
            label_why = "Migration-Fallback"
            
            # Phase 15: Smart Cleaning
            cleaned_name = FilenameCleaner.clean(file_path)
            self.logger.debug(f"[Fallback] Intentando Discogs por nombre de archivo... ({label_why})")
            self.logger.debug(f"[Cleaner] Original: {os.path.basename(file_path)}")
            self.logger.debug(f"[Cleaner] Limpio:   {cleaned_name}")
            
            c_artist, c_title = FilenameCleaner.extract_artist_title(cleaned_name)
            
            if c_artist and c_title:
                self.logger.debug(f"[Cleaner] Detectado: {c_artist} - {c_title}")
                # Search precise
                fallback_res = self.discogs_client.search_releases(artist=c_artist, track_title=c_title, per_page=1).get("results", [])
                fallback_res = fallback_res[0] if fallback_res else None
                if not fallback_res:
                     # Relaxed
                     query = f"{c_artist} - {c_title}"
                     self.logger.debug(f"[Fallback] Re-intentando (RELAJADA): '{query}'")
                     fallback_res = self.discogs_client.search_releases(query=query, per_page=1).get("results", [])
                     fallback_res = fallback_res[0] if fallback_res else None
            else:
                 # Search query
                 self.logger.debug(f"[Cleaner] Buscando por query: '{cleaned_name}'")
                 fallback_res = self.discogs_client.search_releases(query=cleaned_name, per_page=1).get("results", [])
                 fallback_res = fallback_res[0] if fallback_res else None

        # If there was a Discogs fallback, populate
        if fallback_res:
             # Create Result
             discogs_res = DiscogsMatchResult(
                file_path=file_path,
                mb_recording_id=None,
                mb_release_id=None,
                mb_title=fallback_res.get("discogs_title"),
                mb_artist=fallback_res.get("discogs_artist"),
                mb_release_title=fallback_res.get("discogs_album"),
                mb_release_date=None, 
                discogs_release_id=fallback_res.get("discogs_id"),
                discogs_master_id=None,
                discogs_title=fallback_res.get("discogs_title"),
                discogs_album_title=fallback_res.get("discogs_album"),
                discogs_artist=fallback_res.get("discogs_artist"),
                discogs_year=fallback_res.get("discogs_year"),
                discogs_country=None,
                discogs_label=None,
                discogs_catno=None,
                discogs_genre=fallback_res.get("discogs_genre"),
                discogs_styles=fallback_res.get("discogs_styles"),
                discogs_cover_url=fallback_res.get("discogs_cover"),
                discogs_media_format=fallback_res.get("discogs_format"),
                discogs_confidence_label="CONF_FALLBACK_FILENAME",
                discogs_confidence_score=0.95
             )
             
        # 5. Consolidación Final: Discogs OR Spotify
        if discogs_res:
            should_enrich = True
            
            if spotify_used and 'best_spot' in locals() and best_spot:
                 # Normalize
                 spot_artist = (track_meta.artist_main or "").lower()
                 disc_artist = (discogs_res.discogs_artist or "").lower()
                 
                 # Simple Set Jaccard
                 s1 = set(spot_artist.split())
                 s2 = set(disc_artist.split())
                 intersection = len(s1.intersection(s2))
                 union = len(s1.union(s2))
                 sim = intersection / union if union > 0 else 0.0
                 
                 if sim < 0.2: # Totally different artist
                     self.logger.warning(f"[Aviso] Discogs falló (Artista diferente: '{discogs_res.discogs_artist}' vs '{track_meta.artist_main}'), usando metadatos de Spotify como definitivo.")
                     should_enrich = False
                     discogs_res = None # Discard bad match
            
            if should_enrich and discogs_res:
                track_meta = DiscogsMapper.enrich(track_meta, discogs_res)
            
        elif self.use_spotify and self.spotify_client and (not track_meta.title or spotify_used):
             # 5.b. Check if we need a "Hail Mary" Spotify Search (Identity V2)
             if not track_meta.title or track_meta.title == "Unknown Title":
                 identity = self.identity_service.identify_track(file_path)
                 if identity:
                     self.logger.info(f"[Identity] Match via IdentityService: {identity.title} ({identity.artist})")
                     track_meta.title = identity.title
                     track_meta.artist_main = identity.artist
                     track_meta.album = identity.album
                     track_meta.year = identity.year
                     
                     track_meta.ids.spotify_id = identity.id
                     spotify_used = True
             
             if track_meta.title:
                 self.logger.info(f"[Aviso] Discogs falló, usando metadatos de Spotify como definitivo.")

        # 6. Quality Assurance / Enrichment
        # Check for ANY missing critical field
        should_enrich = False
        if not track_meta.album or track_meta.album == "None": should_enrich = True
        if not track_meta.year: should_enrich = True
        if not track_meta.genre_main: should_enrich = True
        if not track_meta.editorial.publisher: should_enrich = True # Label

        if track_meta.title and should_enrich:
             self.logger.info("[QA] Datos incompletos detectados. Iniciando Enriquecimiento...")
             
             if track_meta.artist_main == "Unknown Artist" or "Unknown" in track_meta.title:
                 clean_fname = FilenameCleaner.clean(file_path)
                 c_artist, c_title = FilenameCleaner.extract_artist_title(clean_fname)
                 
                 if c_artist and c_title:
                     self.logger.info(f"[Smart Clean] Fixing dirty metadata for search: '{track_meta.artist_main}' -> '{c_artist}'")
                     track_meta.artist_main = c_artist
                     track_meta.title = c_title
                 else:
                     track_meta.title = clean_fname
                     track_meta.artist_main = "" 
             
             from mp3_autotagger.services.identity import TrackIdentity
             
             # Create simple identity
             current_id = TrackIdentity(
                 artist=track_meta.artist_main,
                 title=track_meta.title,
                 album=track_meta.album,
                 year=str(track_meta.year)
             )
             
             enriched = self.enrichment_service.enrich(current_id, duration_ms=track_meta.audio.duration_ms)
             
             if enriched.album and (not track_meta.album or track_meta.album == "None"):
                 track_meta.album = enriched.album
                 self.logger.info(f"[QA] Álbum recuperado y GUARDADO: {track_meta.album}")
                 
             if enriched.title and enriched.title != track_meta.title:
                  track_meta.title = enriched.title
                  self.logger.info(f"[Correction] Título corregido: {track_meta.title}")
             if enriched.artist and enriched.artist != track_meta.artist_main:
                  track_meta.artist_main = enriched.artist
                  self.logger.info(f"[Correction] Artista corregido: {track_meta.artist_main}")
                 
             if enriched.year and (not track_meta.year):
                 track_meta.year = str(enriched.year)
                 track_meta.editorial.release_date = str(enriched.year)
                 self.logger.info(f"[QA] Año recuperado y GUARDADO: {track_meta.year}")
                 
             if enriched.label and not track_meta.editorial.publisher:
                 track_meta.editorial.publisher = enriched.label
                 self.logger.info(f"[QA] Sello recuperado y GUARDADO: {track_meta.editorial.publisher}")

             if enriched.catalog_number and not track_meta.editorial.catalog_number:
                 track_meta.editorial.catalog_number = enriched.catalog_number
                 self.logger.info(f"[QA] Catálogo recuperado y GUARDADO: {track_meta.editorial.catalog_number}")
                 
             if enriched.genre and (not track_meta.genre_main or track_meta.genre_main == "Electronic"):
                 track_meta.genre_main = enriched.genre
                 
             if enriched.styles:
                 current_styles = set(track_meta.editorial.styles)
                 new_styles = set(enriched.styles)
                 track_meta.editorial.styles = list(current_styles.union(new_styles))
                 self.logger.info(f"[QA] Estilos recuperados: {', '.join(enriched.styles)}")
             if enriched.discogs_release_id and not track_meta.ids.discogs_release_id:
                 track_meta.ids.discogs_release_id = str(enriched.discogs_release_id)
             if enriched.discogs_master_id and not track_meta.ids.discogs_master_id:
                 track_meta.ids.discogs_master_id = str(enriched.discogs_master_id)
             if enriched.discogs_url:
                 track_meta.ids.discogs_release_url = enriched.discogs_url
                 
             if enriched.spotify_id and not track_meta.ids.spotify_id:
                 track_meta.ids.spotify_id = enriched.spotify_id
             if enriched.spotify_url:
                 track_meta.ids.spotify_url = enriched.spotify_url
                 
             if enriched.match_confidence > 0.0:
                 track_meta.match_confidence = enriched.match_confidence
                 self.logger.info(f"[QA] Index de Confianza actualizado por Enriquecimiento: {track_meta.match_confidence:.2f}")

             # Credits (Phase 24)
             if enriched.mastered_by: track_meta.editorial.credits_mastering = enriched.mastered_by
             if enriched.mixed_by: track_meta.editorial.credits_mixing = enriched.mixed_by
             if enriched.remixed_by: track_meta.editorial.remixer = enriched.remixed_by

        # Descargar imagen
        if spotify_used and 'best_spot' in locals() and best_spot:
            track_meta.temp_cover_url = best_spot.cover_url
        if discogs_res and discogs_res.discogs_cover_url:
            track_meta.temp_cover_url = discogs_res.discogs_cover_url
            
        if hasattr(track_meta, "temp_cover_url") and track_meta.temp_cover_url:
             self.logger.debug(f"Descargando portada: {track_meta.temp_cover_url}")
             track_meta.temp_cover_bytes = download_image(track_meta.temp_cover_url)

        return ProcessingResult(
            file_path=file_path,
            track_metadata=track_meta,
            discogs_result=discogs_res,
            spotify_used=spotify_used
        )
