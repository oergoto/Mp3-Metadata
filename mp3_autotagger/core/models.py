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

    # --------------------------------------------------
    # HEURÍSTICA MEJORADA PARA RELEASE
    # --------------------------------------------------
    def best_release(self) -> Optional[MBRelease]:
        """
        Heurística optimizada para DJ:
        1. Releases Official
        2. Releases cuyo título se parezca al de la grabación
        3. Evitar compilatorios genéricos (Best Of, Dance Anthems, etc.)
        4. Priorizar releases más antiguos
        """
        if not (self.mb_recording and self.mb_recording.releases):
            return None

        releases = self.mb_recording.releases
        rec_title = (self.mb_recording.title or "").lower().strip()

        COMPILATION_PATTERNS = [
            "best of",
            "greatest hits",
            "the very best",
            "dance anthems",
            "hits of",
            "mega hits",
            "collection",
            "collections",
            "anthology",
            "various artists",
        ]

        def looks_like_compilation(title: str) -> bool:
            t = title.lower()
            return any(pat in t for pat in COMPILATION_PATTERNS)

        def score_release(rel: MBRelease) -> tuple:
            # 1. Official
            status = (rel.status or "").lower()
            is_official = 1 if status == "official" else 0

            # 2. Coincidencia de títulos
            rel_title = (rel.title or "").lower().strip()
            title_match = 0
            if rec_title and rel_title:
                if rec_title in rel_title or rel_title in rec_title:
                    title_match = 1

            # 3. Penalización compilatorios
            is_compilation = 1 if looks_like_compilation(rel_title) else 0

            # 4. Fecha
            date_str = rel.date or ""
            date_key = date_str if date_str else "9999-99-99"

            return (-is_official, -title_match, is_compilation, date_key)

        sorted_releases = sorted(releases, key=score_release)
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

