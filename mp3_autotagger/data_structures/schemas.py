from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
from datetime import date

# ==============================================================================
# 1. CONSTANTES DE MAPEO TXXX (CUSTOM TAGS)
# ==============================================================================
# Estas son las claves EXACTAS que se escribirán en el campo TXXX del MP3.
# Ejemplo: TXXX:DISCOGS_CATALOG_NUMBER = "FAC 51"

class TXXXKeys:
    # Identificadores Únicos
    MB_TRACK_ID = "MusicBrainz Track Id"
    MB_RELEASE_ID = "MusicBrainz Release Id"
    MB_ARTIST_ID = "MusicBrainz Artist Id"
    MB_WORK_ID = "MusicBrainz Work Id"
    DISCOGS_RELEASE_ID = "Discogs Release Id"
    DISCOGS_MASTER_ID = "Discogs Master Id"
    ACOUSTID_ID = "AcoustID"
    SPOTIFY_ID = "Spotify Track Id"
    
    # Datos Editoriales & Catálogo
    CATALOG_NUMBER = "Catalog Number"
    RELEASE_TYPE = "Release Type"      
    RELEASE_STATUS = "Release Status"  
    MEDIA_FORMAT = "Format"            # Changed from "Media Format" to "Format"
    COUNTRY = "Country"                # Changed from "Release Country" to "Country"
    STYLE = "Styles"                   # Changed from "Genre Style" to "Styles"
    LABEL_URL = "URL Discogs"          # Mapped to WXXX usually, but keeping key if used in TXXX
    
    # Créditos Extendidos
    MASTERED_BY = "Mastered By"
    MIXED_BY = "Mixed By"
    REMIXER = "Remixer"                # TPE4 usually, but TXXX backup
    
    # Sistema
    SOURCE = "Metadata Source"         
    MATCH_METHOD = "Match Method"      

# ==============================================================================
# 2. ENUMS (Vocabulario Controlado)
# ==============================================================================

class ReleaseGroupType(Enum):
    ALBUM = "Album"
    SINGLE = "Single"
    EP = "EP"
    COMPILATION = "Compilation"
    REMIX = "Remix"
    DJMIX = "DJ-mix"
    MIXTAPE = "Mixtape"       # Común en Hip-Hop y música urbana
    LIVE = "Live"             # Grabaciones de conciertos
    SOUNDTRACK = "Soundtrack" # OSTs
    DEMO = "Demo"             # Grabaciones no finales
    BROADCAST = "Broadcast"   # Radio shows / Podcasts
    OTHER = "Other"

class ReleaseStatus(Enum):
    OFFICIAL = "Official"
    PROMOTION = "Promotion"
    BOOTLEG = "Bootleg"       # Incluye "Unofficial" de Discogs
    PSEUDO_RELEASE = "Pseudo-Release"
    WITHDRAWN = "Withdrawn"   # Lanzamientos retirados del mercado
    CANCELLED = "Cancelled"   # Planeados pero nunca lanzados
    WHITE_LABEL = "White Label" # Específico para vinilos de prueba/DJ

class MediaFormat(Enum):
    """Crucial para diferenciar Masterización (Vinyl Rip vs Web DL)."""
    VINYL = "Vinyl"           # Incluye 12", 7", LP
    CD = "CD"                 # Incluye CDr, CD-Single
    DIGITAL = "Digital Media" # WEB, File, AIFF, WAV, MP3
    CASSETTE = "Cassette"
    DVD = "DVD"
    SACD = "SACD"
    OTHER = "Other"

# ==============================================================================
# 3. DATACLASSES (Estructura de Datos)
# ==============================================================================

@dataclass
class ExternalIDs:
    """Almacena todos los IDs foráneos para cruzar bases de datos."""
    musicbrainz_track_id: Optional[str] = None
    musicbrainz_release_id: Optional[str] = None
    musicbrainz_artist_id: Optional[str] = None
    discogs_release_id: Optional[int] = None
    discogs_master_id: Optional[int] = None
    spotify_id: Optional[str] = None
    acoustid_fingerprint: Optional[str] = None
    isrc: Optional[str] = None

@dataclass
class AudioFeatures:
    """Datos psicoacústicos."""
    # REVERTED: BPM and Audio Features Removed (Phase 17 - API 403 Restriction)
    is_explicit: bool = False
    duration_ms: Optional[int] = None

@dataclass
class EditorialMetadata:
    """Datos enriquecidos de catálogo (Discogs/MB)."""
    publisher: Optional[str] = None   # TPUB
    catalog_number: Optional[str] = None # TXXX:Catalog Number
    release_date: Optional[str] = None # TDRC
    country: Optional[str] = None      # TXXX:Country
    media_format: Optional[MediaFormat] = None # TXXX:Format
    release_type: ReleaseGroupType = ReleaseGroupType.OTHER # TXXX:Release Type
    release_status: ReleaseStatus = ReleaseStatus.OFFICIAL # TXXX:Release Status
    styles: List[str] = field(default_factory=list) # TXXX:Styles
    
    # New Fields Phase 20
    copyright: Optional[str] = None    # TCOP
    isrc: Optional[str] = None         # TSRC
    comment: Optional[str] = None      # COMM
    remixer: Optional[str] = None      # TPE4
    
    credits_mastering: Optional[str] = None # TXXX:Mastered By (or specific credit role)
    credits_mixing: Optional[str] = None    # TXXX:Mixed By 
    
@dataclass
class UnifiedTrackData:
    """
    OBJETO MAESTRO.
    Representa un archivo MP3 completamente normalizado y listo para escribir.
    """
    # 1. Identidad Básica (ID3 Core)
    title: str                  # TIT2
    artist_main: str            # TPE1
    album: str                  # TALB
    album_artist: str           # TPE2 (Crucial para Various Artists)
    genre_main: str             # TCON
    track_number: str           # TRCK (ej "1/4")
    disc_number: str            # TPOS (ej "1/1")
    year: str                   # TYER (YYYY)
    
    # 2. Módulos Específicos
    ids: ExternalIDs = field(default_factory=ExternalIDs)
    editorial: EditorialMetadata = field(default_factory=EditorialMetadata)
    audio: AudioFeatures = field(default_factory=AudioFeatures)
    
    # 3. Datos de Sistema
    filepath_original: str = ""
    filename_new: str = ""      # Propuesta de renombrado
    match_confidence: float = 0.0 # 0.0 a 1.0 (Semáforo)
    
    def __post_init__(self):
        """
        Enforce type safety at runtime.
        If mappers pass a list/None where a string is expected, fix it here to prevent downstream crashes.
        """
        # List of string fields to sanitize
        str_fields = ['title', 'artist_main', 'album', 'album_artist', 'genre_main', 
                      'track_number', 'disc_number', 'year']
        
        for field_name in str_fields:
            val = getattr(self, field_name)
            if isinstance(val, list):
                # Flatten list: take first item if exists
                fixed_val = str(val[0]) if val else ""
                setattr(self, field_name, fixed_val)
            elif val is None:
                # None -> Empty string
                setattr(self, field_name, "")
            elif not isinstance(val, str):
                # Int/Float -> String
                setattr(self, field_name, str(val))

    def get_primary_image_url(self) -> Optional[str]:
        """Lógica para decidir qué cover art usar (MB > Discogs > Local)."""
        # Placeholder para implementación futura
        return None

    def to_dict(self) -> Dict:
        """Serialización segura para guardar en JSON/Mongo/SQLite."""
        # Implementación simplificada
        return {
            "title": self.title,
            "artist": self.artist_main,
            "ids": self.ids.__dict__,
            # ... resto de campos
        }
