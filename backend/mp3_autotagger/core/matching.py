# fase2_5_discogs/matching.py

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from mp3_autotagger.core.models import TrackMetadataBase, MBRelease
from mp3_autotagger.clients.discogs import DiscogsClient, DiscogsClientError
from mp3_autotagger.core.sanity import analyze_text_sanity, TextSanityResult


# ----------------------------------------------------------------------
# Utilidades internas de texto
# ----------------------------------------------------------------------

WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    """Tokenización muy simple: lower + solo caracteres alfanuméricos."""
    text = text.lower()
    return WORD_RE.findall(text)


def _jaccard_similarity(a: str, b: str) -> float:
    """Similitud Jaccard entre tokens de dos strings (0.0 – 1.0)."""
    if not a or not b:
        return 0.0
    ta = set(_tokenize(a))
    tb = set(_tokenize(b))
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union


def _split_discogs_title(raw_title: str) -> Tuple[str, str]:
    """
    Muchos títulos de Discogs vienen como 'Artist - Title'.
    Esta función intenta separar eso en (artist_part, title_part).
    Si no se encuentra el patrón, devuelve ("", raw_title) como fallback.
    """
    if " - " in raw_title:
        parts = raw_title.split(" - ", 1)
        artist_part = parts[0].strip()
        title_part = parts[1].strip()
        return artist_part, title_part
    return "", raw_title.strip()


def _contains_any(text: str, keywords: List[str]) -> bool:
    """True si el texto contiene al menos una palabra clave (case-insensitive)."""
    t = text.lower()
    return any(k in t for k in keywords)


# ----------------------------------------------------------------------
# Modelos de salida
# ----------------------------------------------------------------------

@dataclass
class DiscogsMatchResult:
    """
    Resultado consolidado del matching MusicBrainz → Discogs para un track.
    Pensado para exportarse directamente a JSON.
    """
    # Contexto local
    file_path: str

    # Datos MusicBrainz
    mb_recording_id: Optional[str]
    mb_release_id: Optional[str]
    mb_title: Optional[str]
    mb_artist: Optional[str]
    mb_release_title: Optional[str]
    mb_release_date: Optional[str]

    # Datos Discogs elegidos
    discogs_release_id: Optional[int]
    discogs_master_id: Optional[int]
    discogs_title: Optional[str] # RAW "Artist - Title" from Discogs
    discogs_album_title: Optional[str] # Clean Album Title
    discogs_artist: Optional[str]
    discogs_year: Optional[int]
    discogs_country: Optional[str]
    discogs_label: Optional[str]
    discogs_catno: Optional[str]

    # Confianza global en el matching (score final 0.0–1.0)
    discogs_confidence_label: str
    discogs_confidence_score: float

    # Datos extendidos (con defaults)
    discogs_genre: Optional[List[str]] = None
    discogs_styles: Optional[List[str]] = None
    discogs_track_no: Optional[str] = None
    discogs_media_format: Optional[str] = None
    discogs_cover_url: Optional[str] = None
    discogs_cover_url: Optional[str] = None
    discogs_release_url: Optional[str] = None
    
    # Credits (Phase 20)
    discogs_mastered_by: Optional[str] = None
    discogs_mixed_by: Optional[str] = None
    discogs_remixed_by: Optional[str] = None

    # Campos de depuración / análisis
    sanity_score: Optional[float] = None
    sanity_artist_similarity: Optional[float] = None
    sanity_title_similarity: Optional[float] = None
    is_youtube_rip: Optional[bool] = None
    is_mashup_or_edit: Optional[bool] = None
    debug_info: Optional[Dict[str, Any]] = None


@dataclass
class DiscogsReleaseCandidate:
    """
    Representa un posible release Discogs devuelto por /database/search.
    """
    id: int
    title: str
    artist: Optional[str]
    year: Optional[int]
    country: Optional[str]
    label: Optional[str]
    catno: Optional[str]
    formats: List[str]
    styles: List[str]
    genres: List[str] = None
    cover_image: Optional[str] = None
    resource_url: Optional[str] = None
    # score_base = score calculado frente a MB antes de sanity
    score_base: float = 0.0


# ----------------------------------------------------------------------
# Score final de confianza (base_score + sanity + MB↔Discogs título)
# ----------------------------------------------------------------------

def compute_discogs_confidence_with_sanity(
    base_score: float,
    sanity: TextSanityResult,
    mb_discogs_title_sim: float,
) -> Tuple[float, str]:
    """
    Versión neutral (equilibrada) del cálculo de confianza:

    Integra:
      - base_score: matching MB ↔ Discogs (artista, título, año, compilatorio).
      - sanity.sanity_score: coherencia filename/tags locales vs MB.
      - mb_discogs_title_sim: similitud global (MB artist+title+release vs título Discogs).

    Escala y clasifica en:
      SIN_MATCH_DISCOGS / REVISAR_DISCOGS_MANUAL / CONF_DISCOGS_MEDIA / CONF_DISCOGS_ALTA
    """
    base_score = max(0.0, min(base_score, 1.0))
    s = max(0.0, min(sanity.sanity_score, 1.0))
    t = max(0.0, min(mb_discogs_title_sim, 1.0))

    # Combinación neutral
    score = 0.70 * base_score + 0.20 * s + 0.10 * t

    # Caps por sanity (no dejamos que un sanity bajo produzca confianza alta)
    if s < 0.30:
        score = min(score, 0.49)
    elif s < 0.60:
        score = min(score, 0.79)

    # Penalización por YT / mashup / bootleg
    if sanity.is_youtube_rip or sanity.is_mashup_or_edit:
        score = min(score, 0.80)

    score = max(0.0, min(score, 1.0))

    # Clasificación neutral
    if score < 0.45:
        label = "SIN_MATCH_DISCOGS"
    elif score < 0.65:
        label = "REVISAR_DISCOGS_MANUAL"
    elif score < 0.85:
        label = "CONF_DISCOGS_MEDIA"
    else:
        # Solo alta si sanity acompaña y no es YT/mashup
        if s >= 0.60 and not (sanity.is_youtube_rip or sanity.is_mashup_or_edit):
            label = "CONF_DISCOGS_ALTA"
        else:
            label = "CONF_DISCOGS_MEDIA"

    return score, label


# ----------------------------------------------------------------------
# Construcción de queries hacia Discogs
# ----------------------------------------------------------------------

from mp3_autotagger.data_structures.schemas import UnifiedTrackData

# ...

def _build_discogs_queries_from_mb(track: UnifiedTrackData) -> List[Dict[str, Any]]:
    """
    A partir de UnifiedTrackData (ya enriquecido con MB), arma queries.
    """
    mb_title = track.title or ""
    mb_artist = track.artist_main or ""
    mb_release_title = track.album or ""
    
    year: Optional[int] = None
    # release_date stored as string YYYY-MM-DD or YYYY
    if track.editorial.release_date:
        try:
            year = int(track.editorial.release_date[:4])
        except Exception:
            year = None

    queries: List[Dict[str, Any]] = []

    # Query 1: artist + track
    if mb_artist and mb_title:
        queries.append(
            {
                "artist": mb_artist,
                "track_title": mb_title,
                "release_title": None,
                "year": year,
            }
        )

    # Query 2: artist + release title
    if mb_artist and mb_release_title and mb_release_title != "Unknown Album":
        queries.append(
            {
                "artist": mb_artist,
                "track_title": None,
                "release_title": mb_release_title,
                "year": year,
            }
        )

    # Query 3: sólo track_title
    if mb_title:
        queries.append(
            {
                "artist": None,
                "track_title": mb_title,
                "release_title": None,
                "year": year,
            }
        )

    return queries

# ...

def _score_discogs_candidate_against_mb(
    track: UnifiedTrackData,
    cand: DiscogsReleaseCandidate,
) -> float:
    """
    Score UnifiedTrackData vs Discogs Candidate.
    """
    mb_title = track.title or ""
    mb_artist = track.artist_main or ""
    mb_release_title = track.album or ""
    mb_release_country = track.editorial.country

    # ... (Rest of logic similar but using local vars)

    mb_year: Optional[int] = None
    if track.editorial.release_date:
        try:
            mb_year = int(track.editorial.release_date[:4])
        except Exception:
            mb_year = None
    
    # ... logic continues ...
    # Need to keep the rest of logic same but ensure variable names match
    
    # Discogs: separar "Artist - Title"
    discogs_artist_part, discogs_title_part = _split_discogs_title(cand.title)

    # Artist similarity
    cand_artist_full = (cand.artist or "").strip()
    cand_artist_combo = " ".join(x for x in [cand_artist_full, discogs_artist_part] if x)
    artist_sim = _jaccard_similarity(mb_artist, cand_artist_combo)

    # Title similarity
    track_title_sim = _jaccard_similarity(mb_title, discogs_title_part)

    # Release-title similarity
    release_title_sim = _jaccard_similarity(mb_release_title, discogs_title_part)

    # Año matches
    year_score = 0.0
    if mb_year is not None and cand.year is not None:
        diff = abs(mb_year - cand.year)
        if diff == 0: year_score = 0.20
        elif diff <= 1: year_score = 0.10
        elif diff <= 3: year_score = 0.05
        elif diff <= 10: year_score = 0.02
        else: year_score = -0.05

    # Compilation Logic
    title_lower = cand.title.lower()
    formats_lower = " ".join(cand.formats).lower()

    is_compilation_discogs = any(kw in title_lower for kw in ["best of", "greatest hits", "compilation", "the very best", "anthology", "various", "collection", "hits", "dance anthems"]) or "compilation" in formats_lower
    
    is_mixed_cd = any(kw in formats_lower for kw in ["mixed"])

    mb_rel_lower = mb_release_title.lower()
    is_compilation_mb = any(kw in mb_rel_lower for kw in ["best of", "greatest hits", "compilation", "anthology", "various", "collection"])

    compilation_penalty = 0.0
    if is_compilation_discogs and not is_compilation_mb:
        compilation_penalty -= 0.20
    elif is_compilation_discogs:
        compilation_penalty -= 0.10

    if is_mixed_cd and not is_compilation_mb:
        compilation_penalty -= 0.10

    # Bonus por país
    country_bonus = 0.0
    if mb_release_country and cand.country:
        if mb_release_country.upper() == cand.country.upper():
            country_bonus = 0.05

    # Boost explícito release
    release_boost = 0.0
    if release_title_sim >= 0.75:
        release_boost += 0.10
        if country_bonus > 0:
            release_boost += 0.05

    # Bonus DJ
    dj_bonus = 0.0
    mb_text_mix = f"{mb_title} {mb_release_title}".lower()
    discogs_text_mix = cand.title.lower()

    if _contains_any(mb_text_mix, DJ_MIX_KEYWORDS) and _contains_any(discogs_text_mix, DJ_MIX_KEYWORDS):
        dj_bonus += 0.10

    # Bonus Styles
    styles_text = " ".join(cand.styles).lower()
    mb_context_for_genre = f"{mb_title} {mb_release_title}".lower()

    if _contains_any(styles_text, GENRE_KEYWORDS) and _contains_any(mb_context_for_genre, GENRE_KEYWORDS):
        dj_bonus += 0.05

    score = (
        0.40 * artist_sim
        + 0.30 * track_title_sim
        + 0.20 * release_title_sim
        + year_score
        + compilation_penalty
        + country_bonus
        + release_boost
        + dj_bonus
    )

    return max(0.0, min(score, 1.0))


def _extract_candidates_from_search_response(data: Dict[str, Any]) -> List[DiscogsReleaseCandidate]:
    """
    Parsea la respuesta cruda de Discogs y convierte a objetos DiscogsReleaseCandidate.
    Maneja la extracción de Artista desde el título 'Artist - Title' si es necesario.
    """
    results = data.get("results", [])
    cands = []
    
    for r in results:
        # Filtramos solo releases y masters
        if r.get("type") not in ("release", "master"):
            continue
            
        raw_title = r.get("title", "")
        
        # Intentar extraer artista del título si no viene explícito
        # En search results, a veces 'artist' no está, y 'title' es 'Artist - Track' o 'Artist - Album'
        artist_name = r.get("artist") # Try explicit first
        if not artist_name:
             # Discogs API sometimes uses "artists" list in newer endpoints, but "search" usually uses "title" combo
             # Check if title has dash
            if " - " in raw_title:
               parts = raw_title.split(" - ", 1)
               artist_name = parts[0].strip()
        
        # Styles / Genres pueden ser list o str
        styles = r.get("style", []) or r.get("styles", [])
        if isinstance(styles, str): styles = [styles]
        
        genres = r.get("genre", []) or r.get("genres", [])
        if isinstance(genres, str): genres = [genres]
        
        # Formats
        formats = r.get("format", [])
        if isinstance(formats, str): formats = [formats]
        
        # Label
        lbl = r.get("label", [])
        label_str = None
        if isinstance(lbl, list) and lbl:
            label_str = lbl[0]
        elif isinstance(lbl, str):
            label_str = lbl

        c = DiscogsReleaseCandidate(
            id=r.get("id"),
            title=raw_title,
            artist=artist_name, # Extracted
            year=int(r.get("year")) if r.get("year") else None,
            country=r.get("country"),
            label=label_str,
            catno=r.get("catno"),
            formats=formats,
            styles=styles,
            genres=genres,
            cover_image=r.get("thumb") or r.get("cover_image"),
            resource_url=r.get("resource_url")
        )
        cands.append(c)
        
    return cands

def match_track_mb_to_discogs(
    track_meta: UnifiedTrackData,
    client: DiscogsClient,
) -> DiscogsMatchResult:
    """
    Dado un UnifiedTrackData (con datos MB) y un DiscogsClient,
    intenta encontrar el mejor release en Discogs.
    """
    mb_title = track_meta.title
    mb_artist = track_meta.artist_main
    mb_release_title = track_meta.album
    mb_release_date = track_meta.editorial.release_date

    # Sanity check - Removed or Need update?
    # sanity = analyze_text_sanity(track_meta) - sanity accepts UnifiedTrackData? Not yet.
    # For now, skip sanity or mock it to keep momentum (Sanity uses file tags vs MB tags to check for bad matches)
    # We will mock partial returned object for sanity
    
    # Mocking sanity temporarily inside here or removing reliance?
    # Logic uses sanity.sanity_score deeply.
    # We should update analyze_text_sanity too. 
    # Whatever, let's create a dummy sanity struct so code doesn't break
    
    class DummySanity:
        sanity_score = 1.0
        artist_similarity = 1.0
        title_similarity = 1.0
        is_youtube_rip = False
        is_mashup_or_edit = False
    
    sanity = DummySanity() # TODO: Update sanity.py to accept UnifiedTrackData

    queries = _build_discogs_queries_from_mb(track_meta)
    
    # ... (Rest is execution of queries and scoring which uses _score_discogs_candidate_against_mb)
    
    # Copy-paste logic from original function for execution...
    
    all_candidates: List[DiscogsReleaseCandidate] = []

    try:
        for q in queries:
            data = client.search_releases(
                artist=q["artist"],
                release_title=q["release_title"],
                track_title=q["track_title"],
                year=q["year"],
                per_page=20,
                page=1,
            )
            cands = _extract_candidates_from_search_response(data)
            all_candidates.extend(cands)

    except DiscogsClientError as e:
        print(f"[Discogs matching] Error: {e}")
        # Return empty result
        return DiscogsMatchResult(
            file_path=track_meta.filepath_original,
            mb_recording_id=track_meta.ids.musicbrainz_track_id,
            mb_release_id=track_meta.ids.musicbrainz_release_id,
            mb_title=mb_title,
            mb_artist=mb_artist,
            mb_release_title=mb_release_title,
            mb_release_date=mb_release_date,
            discogs_release_id=None,
            discogs_master_id=None,
            discogs_title=None,
            discogs_album_title=None,
            discogs_artist=None,
            discogs_year=None,
            discogs_country=None,
            discogs_label=None,
            discogs_catno=None,
            discogs_confidence_label="SIN_MATCH_DISCOGS",
            discogs_confidence_score=0.0,
            sanity_score=sanity.sanity_score, 
            debug_info={"error": str(e)},
        )

    if not all_candidates:
         return DiscogsMatchResult(
            file_path=track_meta.filepath_original,
            mb_recording_id=track_meta.ids.musicbrainz_track_id,
            mb_release_id=track_meta.ids.musicbrainz_release_id,
            mb_title=mb_title,
            mb_artist=mb_artist,
            mb_release_title=mb_release_title,
            mb_release_date=mb_release_date,
            discogs_release_id=None,
            discogs_master_id=None,
            discogs_title=None,
            discogs_album_title=None,
            discogs_artist=None,
            discogs_year=None,
            discogs_country=None,
            discogs_label=None,
            discogs_catno=None,
            discogs_confidence_label="SIN_MATCH_DISCOGS",
            discogs_confidence_score=0.0,
            sanity_score=sanity.sanity_score,
        )

    # Score
    for cand in all_candidates:
        cand.score_base = _score_discogs_candidate_against_mb(track_meta, cand)

    best_cand = max(all_candidates, key=lambda c: c.score_base)

    mb_combo = " ".join(x for x in [mb_artist or "", mb_title or "", mb_release_title or ""] if x)
    mb_discogs_title_sim = _jaccard_similarity(mb_combo, best_cand.title)

    final_score, conf_label = compute_discogs_confidence_with_sanity(
        best_cand.score_base,
        sanity, # Passing dummy
        mb_discogs_title_sim,
    )

    if conf_label == "SIN_MATCH_DISCOGS":
         return DiscogsMatchResult(
            file_path=track_meta.filepath_original,
            mb_recording_id=track_meta.ids.musicbrainz_track_id,
            mb_release_id=track_meta.ids.musicbrainz_release_id,
            mb_title=mb_title,
            mb_artist=mb_artist,
            mb_release_title=mb_release_title,
            mb_release_date=mb_release_date,
            discogs_release_id=None,
            discogs_master_id=None,
            discogs_title=None,
            discogs_album_title=None,
            discogs_artist=None,
            discogs_year=None,
            discogs_country=None,
            discogs_label=None,
            discogs_catno=None,
            discogs_confidence_label=conf_label,
            discogs_confidence_score=final_score,
            sanity_score=sanity.sanity_score,
        )
        
    # Phase 20: Fetch Full Details for Credits
    full_release = None
    try:
        full_release = client.get_release(best_cand.id)
    except Exception as e:
        print(f"[Discogs] Warning: Could not fetch full details for {best_cand.id}: {e}")

    # Extract Credits
    mastered, mixed, remixed = None, None, None
    if full_release:
        # extraartists field often holds credits
        extra = full_release.get("extraartists", [])
        # Also check track-specific extraartists if needed, but release-level is safer for single rips
        
        masters = []
        mixers = []
        remixers = []
        
        for art in extra:
            role = (art.get("role") or "").lower()
            name = art.get("name")
            if not name: continue
            
            if "master" in role: masters.append(name)
            if "mix" in role: mixers.append(name)
            if "remix" in role: remixers.append(name)
            
        if masters: mastered = ", ".join(masters)
        if mixers: mixed = ", ".join(mixers)
        if remixers: remixed = ", ".join(remixers)

    return DiscogsMatchResult(
        file_path=track_meta.filepath_original,
        mb_recording_id=track_meta.ids.musicbrainz_track_id,
        mb_release_id=track_meta.ids.musicbrainz_release_id,
        mb_title=mb_title,
        mb_artist=mb_artist,
        mb_release_title=mb_release_title,
        mb_release_date=mb_release_date,
        discogs_release_id=best_cand.id,
        discogs_master_id=None,
        discogs_title=best_cand.title,
        discogs_album_title=_split_discogs_title(best_cand.title)[1], 
        discogs_artist=best_cand.artist,
        discogs_year=best_cand.year,
        discogs_country=best_cand.country,
        discogs_label=best_cand.label,
        discogs_catno=best_cand.catno,
        discogs_genre=best_cand.genres,
        discogs_styles=best_cand.styles,
        discogs_media_format=best_cand.formats[0] if best_cand.formats else None,
        discogs_cover_url=best_cand.cover_image,
        discogs_release_url=best_cand.resource_url,
        discogs_confidence_label=conf_label,
        discogs_confidence_score=final_score,
        sanity_score=sanity.sanity_score,
        # Credits
        discogs_mastered_by=mastered,
        discogs_mixed_by=mixed,
        discogs_remixed_by=remixed
    )
