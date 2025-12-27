from typing import Optional, List
from datetime import datetime
import re

from mp3_autotagger.core.models import MBRecording, MBRelease, MBArtist
from mp3_autotagger.core.matching import DiscogsMatchResult
from mp3_autotagger.data_structures.schemas import (
    UnifiedTrackData, ExternalIDs, EditorialMetadata, AudioFeatures, 
    MediaFormat, ReleaseStatus, ReleaseGroupType
)

class MusicBrainzMapper:
    """Consolidates MusicBrainz logic and mapping to UnifiedTrackData."""

    @staticmethod
    def map(recording: MBRecording, original_file_path: str = "") -> UnifiedTrackData:
        # 1. Select Best Release (Heuristic)
        best_rel = MusicBrainzMapper._select_best_release(recording)
        
        # 2. Basic Info
        title = recording.title
        artist = recording.artists[0].name if recording.artists else "Unknown Artist"
        
        # 3. Create Editorial
        editorial = EditorialMetadata()
        if best_rel:
            editorial.release_status = MusicBrainzMapper._map_status(best_rel.status)
            editorial.release_date = best_rel.date
            editorial.country = best_rel.country
            editorial.release_type = MusicBrainzMapper._map_type(best_rel.release_group_type)
            editorial.media_format = MusicBrainzMapper._map_format(best_rel.media_formats)
            
        # 4. Create IDs
        ids = ExternalIDs()
        ids.musicbrainz_track_id = recording.id
        ids.musicbrainz_artist_id = recording.artists[0].id if recording.artists else None
        if recording.isrcs:
            ids.isrc = recording.isrcs[0]
            
        if best_rel:
            ids.musicbrainz_release_id = best_rel.id
        
        # 5. Construct Unified Object
        unified = UnifiedTrackData(
            title=title,
            artist_main=artist,
            album=best_rel.title if best_rel else "Unknown Album",
            album_artist=artist, # Default to track artist for now
            genre_main="Electronic", # MB doesn't give good genres usually
            track_number="", # MB Recording doesn't have track number
            disc_number="1/1",
            year=MusicBrainzMapper._extract_year(best_rel.date) if best_rel else "",
            
            ids=ids,
            editorial=editorial,
            audio=AudioFeatures(),
            
            filepath_original=original_file_path
        )
        
        return unified

    @staticmethod
    def _select_best_release(recording: MBRecording) -> Optional[MBRelease]:
        """
        Heuristic delegates to ReleaseHeuristics module.
        """
        from mp3_autotagger.core.heuristics import ReleaseHeuristics

        if not recording.releases:
            return None

        rec_title = recording.title
        
        # Sort Key using shared heuristic
        sorted_releases = sorted(
            recording.releases, 
            key=lambda r: ReleaseHeuristics.score_release(r, rec_title)
        )
        return sorted_releases[0]

    @staticmethod
    def _map_status(status_str: Optional[str]) -> ReleaseStatus:
        if not status_str:
            return ReleaseStatus.OFFICIAL # Default
        s = status_str.lower()
        if "bootleg" in s: return ReleaseStatus.BOOTLEG
        if "promotion" in s: return ReleaseStatus.PROMOTION
        if "official" in s: return ReleaseStatus.OFFICIAL
        return ReleaseStatus.OFFICIAL

    @staticmethod
    def _extract_year(date_str: Optional[str]) -> str:
        if not date_str: return ""
        return date_str.split("-")[0]

    @staticmethod
    def _map_type(type_str: Optional[str]) -> ReleaseGroupType:
        if not type_str: return ReleaseGroupType.OTHER
        t = type_str.lower()
        if "album" in t: return ReleaseGroupType.ALBUM
        if "single" in t: return ReleaseGroupType.SINGLE
        if "ep" in t: return ReleaseGroupType.EP
        if "compilation" in t: return ReleaseGroupType.COMPILATION
        if "remix" in t: return ReleaseGroupType.REMIX
        if "dj-mix" in t or "dj mix" in t: return ReleaseGroupType.DJMIX
        if "broadcast" in t: return ReleaseGroupType.BROADCAST
        return ReleaseGroupType.OTHER

    @staticmethod
    def _map_format(formats: List[str]) -> MediaFormat:
        if not formats: return MediaFormat.DIGITAL # Default assumption for mp3s
        # Check first format
        f = formats[0].lower()
        if "vinyl" in f or "12\"" in f or "7\"" in f: return MediaFormat.VINYL
        if "cd" in f: return MediaFormat.CD
        if "file" in f or "digital" in f: return MediaFormat.DIGITAL
        if "cassette" in f: return MediaFormat.CASSETTE
        return MediaFormat.OTHER


class DiscogsMapper:
    """Maps DiscogsMatchResult to UnifiedTrackData fields."""
    
    @staticmethod
    def enrich(unified: UnifiedTrackData, result: DiscogsMatchResult) -> UnifiedTrackData:
        """
        Overlays Discogs data onto an existing UnifiedTrackData object.
        Reference: merge strategy -> Discogs overrides MB generic data if available.
        """
        # IDs
        if result.discogs_release_id:
            unified.ids.discogs_release_id = result.discogs_release_id
        if result.discogs_master_id:
            unified.ids.discogs_master_id = result.discogs_master_id
            
        # Editorial
        if result.discogs_label:
            unified.editorial.publisher = result.discogs_label
        if result.discogs_catno:
            unified.editorial.catalog_number = result.discogs_catno
        if result.discogs_genre:
            # First genre
            unified.genre_main = result.discogs_genre[0] if isinstance(result.discogs_genre, list) and result.discogs_genre else str(result.discogs_genre)
        if result.discogs_styles:
             unified.editorial.styles = result.discogs_styles
             
        # Basic override if MB was empty or generic
        # NOTE: In Phase 12 we decided Discogs Album Title is cleaner?
        # Yes, map it if available.
        if result.discogs_album_title:
            unified.album = result.discogs_album_title
        
        # Year override (Discogs often better for electronic)
        if result.discogs_year:
             unified.year = str(result.discogs_year)
             unified.editorial.release_date = str(result.discogs_year) # Approximate
             
        # Format
        if result.discogs_media_format:
            unified.editorial.media_format = DiscogsMapper._map_format(result.discogs_media_format)
            
        # Credits (Phase 20)
        if result.discogs_mastered_by:
            unified.editorial.credits_mastering = result.discogs_mastered_by
        if result.discogs_mixed_by:
            unified.editorial.credits_mixing = result.discogs_mixed_by
        if result.discogs_remixed_by:
            unified.editorial.remixer = result.discogs_remixed_by
        
        # Country Override (if MB missing) - Discogs often better
        if result.discogs_country and not unified.editorial.country:
             unified.editorial.country = result.discogs_country
        
        # URL (Phase 24)
        if result.discogs_release_id:
             # Reconstruct browsable URL safe fallback
             unified.ids.discogs_release_url = f"https://www.discogs.com/release/{result.discogs_release_id}"
            
        return unified

    @staticmethod
    def _map_format(fmt_input: any) -> MediaFormat:
        if isinstance(fmt_input, list):
            f = fmt_input[0].lower() if fmt_input else ""
        elif isinstance(fmt_input, str):
            f = fmt_input.lower()
        else:
            f = ""
        if "vinyl" in f: return MediaFormat.VINYL
        if "7\"" in f: return MediaFormat.VINYL
        if "12\"" in f: return MediaFormat.VINYL
        if "lp" in f: return MediaFormat.VINYL
        if "cd" in f: return MediaFormat.CD
        if "file" in f or "web" in f or "digital" in f or "320" in f: return MediaFormat.DIGITAL
        return MediaFormat.OTHER
