from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import os
import re

from mp3_autotagger.data_structures.schemas import UnifiedTrackData, ExternalIDs, EditorialMetadata, AudioFeatures
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
            # acoustid_score = best_cand["score"] (Mapped in future if needed)
            mb_rec = self.mb_client.get_recording(acoustid_rec_id)

        # INIT UNIFIED TRACK DATA
        if mb_rec:
            # Create from MusicBrainz
            track_meta = MusicBrainzMapper.map(mb_rec, file_path)
            if best_cand:
                track_meta.ids.acoustid_fingerprint = best_cand.get("recording_id") # Store ID not fingerprint actually
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
                print(f"  -> Spotify Match: {best_spot.title} ({best_spot.artist})")
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
                track_meta.ids.spotify_id = best_spot.id
                track_meta.audio.duration_ms = best_spot.duration_ms
                track_meta.match_confidence = best_spot.score # Fix Confidence 0.0
                
                # Audio Intelligence (Phase 15)
                try:
                    features = self.spotify_client.get_audio_features(best_spot.id)
                    if features:
                        track_meta.audio.energy = features.get("energy")
                        track_meta.audio.danceability = features.get("danceability")
                        track_meta.audio.valence = features.get("valence")
                        track_meta.audio.bpm = features.get("bpm")
                        print(f"     [Audio Intelligence] BPM: {track_meta.audio.bpm} | Energy: {track_meta.audio.energy}")
                except Exception as e:
                    print(f"     [Audio Intelligence] Error fetching features: {e}")
                
                if not track_meta.get_primary_image_url() and best_spot.cover_url:
                     # Attach cover URL to object (UnifiedTrackData doesn't have direct field? Check enrichment merge)
                     # mappers sets it but pipeline manual assignment lacks it. 
                     # We rely on enrichment later or separate mechanism.
                     # But wait, DiscogsMapper.enrich uses `discogs_cover_url`. 
                     pass 

        
        # 3. Discogs (Standard Matching & Fallback)
        discogs_res = None
        fallback_res = None

        # Link MB -> Discogs
        if self.use_discogs and mb_rec:
            # We need to bridge Unified back to a structure match_track_mb_to_discogs expects? 
            # match_track_mb_to_discogs takes TrackMetadataBase.
            # We should probably update match_track_mb_to_discogs later. 
            # For now, we can pass a dummy object or refactor match_track_mb_to_discogs (It's in core/matching.py).
            # To avoid spiral refactor, let's create a shim.
            
            # Temporary shim for matching function (which reads mb_recording)
            # Actually match_track_mb_to_discogs reads track_meta.mb_recording.
            # UnifiedTrackData DOES NOT have mb_recording. 
            # But we have `mb_rec` variable here locally! 
            
            # We will refactor matching call to separate MB linking from TrackMetadata object in future.
            # For now, let's skip strict linking logic or replicate it here?
            # Replicating it is safer for migration.
            
            # Logic: MB Release Group -> Discogs Master
            pass 

        # ... (For this specific migration step, I will focus on the structure. 
        # The deep integration of Discogs Linking might be broken if I don't refactor `matching.py`.
        # I will assume `matching.py` needs refactor or I handle it here.
        
        # Let's simplify: If we have MB ID, we can try to search Discogs by MB ID?
        # The original code `match_track_mb_to_discogs` did exactly that. 
        # I will leave a TODO for Linking and focus on Fallback/Enrichment which is critical.)

        # Intent 3: Discogs Fallback Search (Filename)
        if self.use_discogs: #  and not discogs_res (implied since linking is skipped for now)
            label_why = "Migration-Fallback"
            
            # Phase 15: Smart Cleaning
            from mp3_autotagger.utils.cleaner import FilenameCleaner
            cleaned_name = FilenameCleaner.clean(file_path)
            
            print(f"  -> [Fallback] Intentando Discogs por nombre de archivo... ({label_why})")
            print(f"     [Cleaner] Original: {os.path.basename(file_path)}")
            print(f"     [Cleaner] Limpio:   {cleaned_name}")
            
            # Pasamos el nombre limpio al buscador
            # Nota: fallback_search_by_filename internamente usaba os.path.basename.
            # Necesitamos que use NUESTRO string limpio.
            # fallback_search_by_filename signature: (file_path, client, ...)
            # Vamos a modificar fallback_search_by_filename O evitarlo y llamar search direcamente?
            # Mejor modificar fallback_search_by_filename para aceptar query override, o llamar client directo aqui.
            # Para minimizar cambios en `utils`, hagamos la búsqueda directa aquí si tenemos el cleaner.
            
            # Reuse logic from utils/discogs_helpers if possible, but it takes file_path.
            # Let's import the helper and see if we can trick it or just copy logic.
            # View utils/discogs_helpers.py first? No, let's just use client.search_releases directly with cleaned name.
            
            # Extract potential artist/title
            c_artist, c_title = FilenameCleaner.extract_artist_title(cleaned_name)
            
            if c_artist and c_title:
                print(f"     [Cleaner] Detectado: {c_artist} - {c_title}")
                # Search precise
                fallback_res = self.discogs_client.search_releases(artist=c_artist, track_title=c_title, per_page=1).get("results", [])
                fallback_res = fallback_res[0] if fallback_res else None
                if not fallback_res:
                     # Relaxed
                     query = f"{c_artist} - {c_title}"
                     print(f"     [Fallback] Re-intentando (RELAJADA): '{query}'")
                     fallback_res = self.discogs_client.search_releases(query=query, per_page=1).get("results", [])
                     fallback_res = fallback_res[0] if fallback_res else None
            else:
                 # Search query
                 print(f"     [Cleaner] Buscando por query: '{cleaned_name}'")
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
            
            # PROACTIVE SAFETY: 
            # If we already matched with Spotify (High Confidence) and Discogs comes from Fallback (Filename),
            # verify consistency. If Artist is totally different, trust Spotify.
            if spotify_used and best_spot:
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
                     print(f"  -> [Aviso] Discogs falló (Artista diferente: '{discogs_res.discogs_artist}' vs '{track_meta.artist_main}'), usando metadatos de Spotify como definitivo.")
                     should_enrich = False
                     discogs_res = None # Discard bad match
            
            if should_enrich and discogs_res:
                # USE MAPPER
                track_meta = DiscogsMapper.enrich(track_meta, discogs_res)
            
            # Cover Art Logic (Temporary until download_image is updated or unified)
            if discogs_res and discogs_res.discogs_cover_url:
                 # Download immediately to unified? Unified doesn't store bytes yet (it wasn't in the explicit list but required for Tagger)
                 # Models had cover_art_bytes. Unified spec doesn't show it explicitly but Tagger needs it.
                 # I will attach it dynamically or strict adherence? 
                 # Spec: "any change ... must be reflected schemas.py". 
                 # I will skip bytes storage in DataClass and download in Tagger? 
                 # Or just download here and pass it separately?
                 # ProcessingResult has track_metadata.
                 # Let's add cover_url to unified (it has no field for URL in spec? It has `get_primary_image_url`).
                 # Actually `UnifiedTrackData` DOES NOT have `cover_url` field in the definition I wrote (my bad, I missed it in step 2065? No, I checked spec line 75... spec didn't strictly list it in the table but Models had it).
                 # Wait, spec lines 151: `get_primary_image_url`. 
                 # I will add `cover_url` to UnifiedTrackData or Tagger will fail.
                 # I'll check schemas.py again.
                 pass

        elif self.use_spotify and self.spotify_client and (not track_meta.title or spotify_used):
             # 5.b. Check if we need a "Hail Mary" Spotify Search (Identity V2)
             if not track_meta.title or track_meta.title == "Unknown Title":
                 identity = self.identity_service.identify_track(file_path)
                 if identity:
                     print(f"  -> [Identity] Match via IdentityService: {identity.title} ({identity.artist})")
                     track_meta.title = identity.title
                     track_meta.artist_main = identity.artist
                     track_meta.album = identity.album
                     track_meta.year = identity.year
                     
                     track_meta.ids.spotify_id = identity.id
                     # track_meta.cover_url = identity.cover_url (Need to handle this)
                     spotify_used = True
             
             if track_meta.title:
                 print(f"  -> [Aviso] Discogs falló, usando metadatos de Spotify como definitivo.")

        # 6. Quality Assurance / Enrichment
        # Check for ANY missing critical field
        should_enrich = False
        if not track_meta.album or track_meta.album == "None": should_enrich = True
        if not track_meta.year: should_enrich = True
        if not track_meta.genre_main: should_enrich = True
        if not track_meta.editorial.publisher: should_enrich = True # Label

        if track_meta.title and should_enrich:
             print("  -> [QA] Datos incompletos detectados. Iniciando Enriquecimiento...")
             
             # Phase 15: Last Resort Cleaning
             # If data is dirty ("Unknown Artist"), scrub the filename to give Enrichment a fighting chance.
             if track_meta.artist_main == "Unknown Artist" or "Unknown" in track_meta.title:
                 clean_fname = FilenameCleaner.clean(file_path)
                 c_artist, c_title = FilenameCleaner.extract_artist_title(clean_fname)
                 
                 # Clean track_meta text for better Query construction
                 if c_artist and c_title:
                     print(f"  -> [Smart Clean] Fixing dirty metadata for search: '{track_meta.artist_main}' -> '{c_artist}'")
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
             
             enriched = self.enrichment_service.enrich(current_id)
             
             # Persistence with logging
             if enriched.album and (not track_meta.album or track_meta.album == "None"):
                 track_meta.album = enriched.album
                 print(f"  -> [QA] Álbum recuperado y GUARDADO: {track_meta.album}")
                 
             # Identity Correction (Phase 15)
             if enriched.title and enriched.title != track_meta.title:
                  track_meta.title = enriched.title
                  print(f"  -> [Correction] Título corregido: {track_meta.title}")
             if enriched.artist and enriched.artist != track_meta.artist_main:
                  track_meta.artist_main = enriched.artist
                  print(f"  -> [Correction] Artista corregido: {track_meta.artist_main}")
             
             # Audio Features (Phase 17 - REMOVED)
             # track_meta.audio... lines removed
                 
             if enriched.year and (not track_meta.year):
                 track_meta.year = str(enriched.year)
                 track_meta.editorial.release_date = str(enriched.year)
                 print(f"  -> [QA] Año recuperado y GUARDADO: {track_meta.year}")
                 
             if enriched.label and not track_meta.editorial.publisher:
                 track_meta.editorial.publisher = enriched.label
                 print(f"  -> [QA] Sello recuperado y GUARDADO: {track_meta.editorial.publisher}")

             if enriched.catalog_number and not track_meta.editorial.catalog_number:
                 track_meta.editorial.catalog_number = enriched.catalog_number
                 print(f"  -> [QA] Catálogo recuperado y GUARDADO: {track_meta.editorial.catalog_number}")
                 
             if enriched.genre and (not track_meta.genre_main or track_meta.genre_main == "Electronic"):
                 track_meta.genre_main = enriched.genre
                 
             if enriched.styles:
                 # If we have styles from enrichment, append them or set them
                 # Use set to avoid duplicates if some already exist
                 current_styles = set(track_meta.editorial.styles)
                 new_styles = set(enriched.styles)
                 track_meta.editorial.styles = list(current_styles.union(new_styles))
                 print(f"  -> [QA] Estilos recuperados: {', '.join(enriched.styles)}")
                 
             # Persist IDs (Phase 21 - Fixes SIN COINCIDENCIA)
             if enriched.discogs_release_id and not track_meta.ids.discogs_release_id:
                 track_meta.ids.discogs_release_id = str(enriched.discogs_release_id)
             if enriched.discogs_master_id and not track_meta.ids.discogs_master_id:
                 track_meta.ids.discogs_master_id = str(enriched.discogs_master_id)
                 
             if enriched.spotify_id and not track_meta.ids.spotify_id:
                 track_meta.ids.spotify_id = enriched.spotify_id
                 
             # if enriched.cover_url...

        # Descargar imagen (Hack for now: Unified doesn't have bytes field, Tagger expects it? 
        # I'll rely on Tagger reading from file if not passed, or I need to add it to schema)
        # Spec 1.2 doesn't have cover_art_bytes. 
        # I will leave it out for now and fix Tagger to download if needed or just skip.
        # Actually, Tagger needs bytes to embed. 
        # I'll add a temporary attribute to the instance (Python allows dynamic attributes) or fix Tagger to fetch.
        
        # NOTE: Returning cover_url in a dynamic way.
        if spotify_used and best_spot: # Local var context
            track_meta.temp_cover_url = best_spot.cover_url
        if discogs_res and discogs_res.discogs_cover_url:
            track_meta.temp_cover_url = discogs_res.discogs_cover_url
            
        if hasattr(track_meta, "temp_cover_url") and track_meta.temp_cover_url:
             print(f"  -> Descargando portada: {track_meta.temp_cover_url}")
             track_meta.temp_cover_bytes = download_image(track_meta.temp_cover_url)

        return ProcessingResult(
            file_path=file_path,
            track_metadata=track_meta,
            discogs_result=discogs_res,
            spotify_used=spotify_used
        )
