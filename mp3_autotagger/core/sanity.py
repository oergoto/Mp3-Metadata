# fase2_5_discogs/text_sanity.py

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional, Set

from mp3_autotagger.core.models import TrackMetadataBase


WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> Set[str]:
    """Tokenización simple: lower-case y solo caracteres alfanuméricos."""
    text = text.lower()
    return set(WORD_RE.findall(text))


def _similarity(a: str, b: str) -> float:
    """Similitud Jaccard de tokens entre dos strings (0.0 – 1.0)."""
    if not a or not b:
        return 0.0
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union


@dataclass
class TextSanityResult:
    sanity_score: float
    artist_similarity: float
    title_similarity: float
    is_youtube_rip: bool
    is_mashup_or_edit: bool


def analyze_text_sanity(track: TrackMetadataBase) -> TextSanityResult:
    """
    Compara filename + tags originales vs artist/title de MusicBrainz
    y detecta patrones típicos de YT/mashups.

    Se apoya ÚNICAMENTE en métodos de TrackMetadataBase:
      - track.file_path
      - track.original_tags (dict opcional con TIT2 / TPE1)
      - track.main_artist_name()
      - track.main_title()
    """
    # --- 1) Texto base local: filename + tags originales ---
    basename = os.path.basename(track.file_path)
    basename_no_ext, _ = os.path.splitext(basename)
    basename_no_ext = basename_no_ext.replace("_", " ")

    # Tags originales (si existen en TrackMetadataBase)
    original_tags = getattr(track, "original_tags", None) or {}

    tag_title = str(original_tags.get("TIT2", "")).strip()
    tag_artist = str(original_tags.get("TPE1", "")).strip()

    local_text_title = f"{basename_no_ext} {tag_title}".strip()
    local_text_artist = f"{basename_no_ext} {tag_artist}".strip()

    # --- 2) Texto MusicBrainz: artista principal + título principal ---
    mb_artist = track.main_artist_name() or ""
    mb_title = track.main_title() or ""

    # Similitudes específicas
    artist_sim = max(
        _similarity(local_text_artist, mb_artist),
        _similarity(tag_artist, mb_artist),
    )

    title_sim = max(
        _similarity(local_text_title, mb_title),
        _similarity(tag_title, mb_title),
    )

    # Sanity global: comparar todo el texto local vs "artist title"
    mb_combo = f"{mb_artist} {mb_title}".strip()
    sanity_score = max(
        _similarity(basename_no_ext, mb_combo),
        _similarity(f"{tag_artist} {tag_title}".strip(), mb_combo),
        (artist_sim + title_sim) / 2.0 if (artist_sim or title_sim) else 0.0,
    )

    # --- 3) Flags especiales YT/mashup ---
    full_local_text = " ".join(
        [
            basename.lower(),
            tag_title.lower(),
            tag_artist.lower(),
        ]
    )

    yt_patterns = [
        "y2mate",
        "youtube",
        "youtu.be",
        "web-rip",
        "webrip",
        "soundcloud",
        "mixcloud",
        "rip ",
        " rip-",
        "rip]",
        "[free download]",
        " free download",
        " [free]",
    ]

    mashup_patterns = [
        "mashup",
        "bootleg",
        "rework",
        "re-edit",
        "re edit",
        "private edit",
        "extended edit",
        "unofficial",
        " vs ",
        " vs.",
        "vs.",
        " edit by ",
        "bootleg mix",
    ]

    is_youtube_rip = any(pat in full_local_text for pat in yt_patterns)
    is_mashup_or_edit = any(pat in full_local_text for pat in mashup_patterns)

    return TextSanityResult(
        sanity_score=sanity_score,
        artist_similarity=artist_sim,
        title_similarity=title_sim,
        is_youtube_rip=is_youtube_rip,
        is_mashup_or_edit=is_mashup_or_edit,
    )
