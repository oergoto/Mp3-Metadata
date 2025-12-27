from dataclasses import dataclass
from typing import Optional, List
import os
import re

from mp3_autotagger.clients.spotify import SpotifyClient
from mp3_autotagger.clients.musicbrainz import MusicBrainzClient
from mp3_autotagger.config import CONFIDENCE_THRESHOLD_HIGH
from mp3_autotagger.core.acoustid import identify_with_acoustid, analyze_file
from mp3_autotagger.core.fallback import clean_filename

@dataclass
class TrackIdentity:
    """Standardized Identity of a track found by any service."""
    artist: str
    title: str
    album: Optional[str] = None
    year: Optional[int] = None
    
    # Source IDs
    mb_recording_id: Optional[str] = None
    spotify_id: Optional[str] = None
    confidence: float = 0.0
    source: str = "unknown" # 'acoustid', 'spotify', 'mb'
    
    cover_url: Optional[str] = None

class IdentityService:
    def __init__(self, spotify_client: Optional[SpotifyClient], mb_client: Optional[MusicBrainzClient]):
        self.spotify = spotify_client
        self.mb = mb_client

    def identify_track(self, file_path: str) -> Optional[TrackIdentity]:
        """
        Intelligent identification strategy:
        1. AcoustID (High precision, ignores filenames).
        2. Spotify Broad Search (Best text parsing).
        3. MusicBrainz Search (Structuring).
        """
        filename = os.path.basename(file_path)
        
        # 1. Try AcoustID
        # (Simplified logic for now, can expand later)
        
        # 2. Try Spotify "Hail Mary" (Broad Search)
        # This is often the most resilient method for "Theuss - STB (Original Mix)"
        if self.spotify:
            clean_name = clean_filename(filename)
            # Remove "Original Mix" from SCORING reference (as learned in Phase 9)
            ref_tit = clean_name
            if " - " in clean_name:
                parts = clean_name.split(" - ", 1)
                ref_tit = parts[1]
            
            ref_tit_clean = re.sub(r"\((original|extended|club|remix|mix|edit|vocal|dub).*?\)", "", ref_tit, flags=re.IGNORECASE).strip()
            
            print(f"  -> [Identity] Searching Spotify for: '{ref_tit_clean}'")
            results = self.spotify.search_broad(clean_name, ref_artist="", ref_title=ref_tit_clean)
            
            if results:
                best = results[0]
                
                # STRICT VALIDATION
                is_valid = True
                
                # 1. Score Check
                if best.score < CONFIDENCE_THRESHOLD_HIGH:
                    print(f"     [Strict] Identity descartada por bajo score ({best.score:.2f})")
                    is_valid = False
                    
                # 2. Duration Check
                if is_valid and best.duration_ms:
                    local_info = analyze_file(file_path)
                    if local_info["duration"]:
                        diff = abs(local_info["duration"] - (best.duration_ms / 1000.0))
                        if diff > 5.0:
                             print(f"     [Strict] Identity descartada por duración (Diff: {diff:.1f}s)")
                             is_valid = False

                if is_valid:
                    print(f"  -> [Identity] Spotify Identified: {best.title} ({best.artist}) [Score={best.score:.2f}]")
                    return TrackIdentity(
                        artist=best.artist,
                        title=best.title,
                        album=best.album,
                        year=best.year,
                        spotify_id=best.id,
                        confidence=best.score,
                        source="spotify",
                        cover_url=best.cover_url
                    )

        # 3. Fallback to MusicBrainz (Existing logic would go here)
        return None
