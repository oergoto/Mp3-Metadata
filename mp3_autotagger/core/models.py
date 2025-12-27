from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ------------------------------------------------------
# ARTIST
# ------------------------------------------------------
@dataclass
class MBArtist:
    id: str
    name: str
    sort_name: Optional[str] = None


# ------------------------------------------------------
# RELEASE
# ------------------------------------------------------
@dataclass
class MBRelease:
    id: str
    title: str
    date: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    release_group_id: Optional[str] = None
    release_group_type: Optional[str] = None
    media_formats: List[str] = field(default_factory=list)


# ------------------------------------------------------
# RECORDING
# ------------------------------------------------------
@dataclass
class MBRecording:
    id: str
    title: str
    length: Optional[int] = None  # milisegundos
    artists: List[MBArtist] = field(default_factory=list)
    releases: List[MBRelease] = field(default_factory=list)
    releases: List[MBRelease] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    isrcs: List[str] = field(default_factory=list)


# ------------------------------------------------------
# TRACK METADATA BASE (Fase 1 + Fase 2)
# ------------------------------------------------------
@dataclass
class TrackMetadataBase:
    """
    Metadatos consolidados de un track.
    Combina:
    - Info local (tags, duración)
    - Resultado AcoustID (recording_id + score)
    - Enriquecimiento MusicBrainz (artistas, releases, título)
    """

    file_path: str
    duration_seconds: Optional[float] = None
    original_tags: Dict[str, Any] = field(default_factory=dict)

    acoustid_recording_id: Optional[str] = None
    acoustid_score: Optional[float] = None

    mb_recording: Optional[MBRecording] = None

    # Enriquecimiento adicional (Discogs o MB detallado)
    genre: Optional[List[str]] = None
    styles: Optional[List[str]] = None
    label: Optional[str] = None
    country: Optional[str] = None
    track_number: Optional[str] = None
    total_tracks: Optional[str] = None
    disc_number: Optional[str] = None
    total_discs: Optional[str] = None
    media_format: Optional[str] = None
    cover_url: Optional[str] = None
    cover_art_bytes: Optional[bytes] = None
    release_url: Optional[str] = None

    display_title: Optional[str] = None
    display_artist: Optional[str] = None
    
    # New fields for Spotify/Enrichment
    album: Optional[str] = None
    year: Optional[str] = None

    # --------------------------------------------------
    # ACCESORS
    # --------------------------------------------------
    def main_artist_name(self) -> Optional[str]:
        if self.display_artist:
            return self.display_artist
        if self.mb_recording and self.mb_recording.artists:
            return self.mb_recording.artists[0].name
        return None

    def main_title(self) -> Optional[str]:
        if self.display_title:
            return self.display_title
        if self.mb_recording:
            return self.mb_recording.title
        return None

    # Logic moved to heuristics.py
    def get_best_release(self) -> Optional[MBRelease]:
        """
        Delegates to ReleaseHeuristics.
        """
        from mp3_autotagger.core.heuristics import ReleaseHeuristics
        
        if not (self.mb_recording and self.mb_recording.releases):
            return None
            
        releases = self.mb_recording.releases
        rec_title = self.mb_recording.title
        
        # Sort using the heuristic key
        sorted_releases = sorted(
            releases, 
            key=lambda r: ReleaseHeuristics.score_release(r, rec_title)
        )
        return sorted_releases[0] if sorted_releases else None


# ------------------------------------------------------
# GENERIC TRACK (Search Result)
# ------------------------------------------------------
@dataclass
class Track:
    """
    Representación genérica de un track obtenido de una fuente externa (Beatport, Juno, etc).
    Used for search results.
    """
    title: str
    artist: str
    album: Optional[str] = None
    label: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[str] = None
    cover_url: Optional[str] = None
    duration_ms: Optional[int] = None
    source: str = "Unknown"
    score: float = 0.0
    id: Optional[str] = None
    url: Optional[str] = None

