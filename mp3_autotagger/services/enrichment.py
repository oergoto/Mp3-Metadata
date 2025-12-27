from typing import Optional, List
from dataclasses import dataclass
from mp3_autotagger.services.identity import TrackIdentity
from mp3_autotagger.clients.discogs import DiscogsClient
from mp3_autotagger.clients.spotify import SpotifyClient
import re

@dataclass
class EnrichedMetadata:
    artist: str
    title: str
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    label: Optional[str] = None
    catalog_number: Optional[str] = None
    cover_url: Optional[str] = None
    styles: List[str] = None # Added for Phase 14
    styles: List[str] = None # Added for Phase 14
    discogs_release_id: Optional[int] = None # Phase 21
    discogs_master_id: Optional[int] = None # Phase 21
    spotify_id: Optional[str] = None # Phase 23
    
    # New Phase 24: Credits & URLs
    mastered_by: Optional[str] = None
    mixed_by: Optional[str] = None
    remixed_by: Optional[str] = None
    discogs_url: Optional[str] = None
    spotify_url: Optional[str] = None

class EnrichmentService:
    def __init__(self, discogs_client: Optional[DiscogsClient], spotify_client: Optional[SpotifyClient] = None):
        self.discogs = discogs_client
        self.spotify = spotify_client

    def _enrich_from_discogs(self, final: EnrichedMetadata) -> EnrichedMetadata:
        """Helper to run Discogs search/enrichment on the current final metadata."""
        if not self.discogs:
            return final

        print(f"  -> [Enrichment] Buscando '{final.artist} - {final.title}' en Discogs...")
        try:
            # 1. Normal Search
            res = self.discogs.search_releases(
                artist=final.artist,
                track_title=final.title,
                year=final.year,
                per_page=5
            )
            candidates = res.get("results", [])
            
            # 2. Swapped Search (Phase 16 Fix)
            # If normal search fails, it might be an inverted filename (Title - Artist)
            if not candidates:
                 print(f"  -> [Enrichment] 0 resultados. Intentando búsqueda INVERTIDA (Title - Artist)...")
                 res = self.discogs.search_releases(
                    artist=final.title,   # Swap
                    track_title=final.artist, # Swap
                    year=final.year,
                    per_page=5
                 )
                 candidates = res.get("results", [])
                 if candidates:
                     print(f"     -> [Fix] Búsqueda Invertida EXITOSA. Corrigiendo Identidad...")
                     # Swap Identity permanently
                     real_artist = final.title
                     real_title = final.artist
                     final.artist = real_artist
                     final.title = real_title
                     # Proceed with processing...

            best_cand = None
            for c in candidates:
                if c.get("type") == "release":
                    best_cand = c
                    break
            
            if best_cand:
                print(f"  -> [Enrichment] Discogs Match: {best_cand.get('title')}")
                
                # Extract Album
                discogs_full_title = best_cand.get("title", "")
                clean_album = discogs_full_title
                if " - " in discogs_full_title:
                    clean_album = discogs_full_title.split(" - ", 1)[1]
                
                if not final.album:
                    final.album = clean_album
                
                # Extract Year
                if not final.year and best_cand.get("year"):
                    raw_year = str(best_cand.get("year"))
                    match_year = re.search(r"(\d{4})", raw_year)
                    if match_year:
                        final.year = int(match_year.group(1))

                if not final.label and best_cand.get("label"):
                    lbl = best_cand.get("label")
                    final.label = lbl[0] if isinstance(lbl, list) and lbl else (lbl if isinstance(lbl, str) else None)
                    print(f"     -> Label encontrado: {final.label}")
                    
                if not final.catalog_number and best_cand.get("catno"):
                    final.catalog_number = best_cand.get("catno")
                    
                # Capture IDs (Phase 21)
                if best_cand.get("id"):
                    final.discogs_release_id = best_cand.get("id")
                if best_cand.get("master_id"):
                    final.discogs_master_id = best_cand.get("master_id")
                    
                # Authority Strategy (Phase 21)
                if final.label and final.catalog_number:
                    print(f"     -> [Authority] Discogs Authority Confirmed (Label: {final.label}, Cat: {final.catalog_number})")

                if not final.genre and best_cand.get("genre"):
                    g = best_cand.get("genre")
                    if isinstance(g, list) and g:
                        final.genre = g[0] 
                    elif isinstance(g, str):
                        final.genre = g
                
                # Capture Styles (Phase 14 - Aggressive)
                styles = best_cand.get("style") or best_cand.get("styles") or []
                
                # AGGRESSIVE MODE: Deep Fetch
                # Always needed for Credits (Phase 24) or missing Styles
                should_deep_fetch = (not styles) or (not final.mastered_by and not final.mixed_by)
                
                if best_cand.get("id"):
                    # Construct Browsable URL
                    final.discogs_url = f"https://www.discogs.com/release/{best_cand.get('id')}"
                    
                    if should_deep_fetch:
                        print(f"  -> [Enrichment] Iniciando Deep Fetch para Créditos/Estilos (Release {best_cand.get('id')})...")
                        try:
                            rel_id = best_cand.get("id")
                            if rel_id:
                                full_rel = self.discogs.get_release(rel_id)
                                if full_rel:
                                    # Styles
                                    new_styles = full_rel.get("styles") or full_rel.get("style") or []
                                    if new_styles:
                                        styles = new_styles
                                        print(f"     -> Deep Fetch Exitoso: {len(styles)} estilos.")
                                    
                                    # Genres
                                    new_genres = full_rel.get("genres") or full_rel.get("genre")
                                    if new_genres:
                                        g = new_genres
                                        if isinstance(g, list) and g:
                                            final.genre = g[0]
                                        elif isinstance(g, str):
                                            final.genre = g
                                            
                                    # Credits (Phase 24)
                                    extra = full_rel.get("extraartists", [])
                                    masters, mixers, remixers = [], [], []
                                    for art in extra:
                                        role = (art.get("role") or "").lower()
                                        name = art.get("name")
                                        if not name: continue
                                        if "master" in role: masters.append(name)
                                        if "mix" in role: mixers.append(name)
                                        if "remix" in role: remixers.append(name)
                                    
                                    if masters: final.mastered_by = ", ".join(masters)
                                    if mixers: final.mixed_by = ", ".join(mixers)
                                    if remixers: final.remixed_by = ", ".join(remixers)
                                    if masters or mixers:
                                        print(f"     -> Deep Fetch Créditos: M={bool(masters)} Mx={bool(mixers)} R={bool(remixers)}")
                                        
                        except Exception as e:
                            print(f"     -> Deep Fetch Falló: {e}")
                            
                final.styles = styles

                if not final.cover_url and best_cand.get("thumb"):
                        final.cover_url = best_cand.get("thumb")

        except Exception as e:
            print(f"  -> [Enrichment] Fallo en Discogs: {e}")

        return final

    def enrich(self, identity: TrackIdentity) -> EnrichedMetadata:
        """
        Takes a basic identity (Artist/Title) and finds richness.
        Priorities: Discogs (Normal/Swap) -> Spotify -> (Loopback Discogs).
        """
        final = EnrichedMetadata(
            artist=identity.artist,
            title=identity.title,
            album=identity.album,
            year=identity.year,
            cover_url=identity.cover_url,
            spotify_id=identity.spotify_id # Initialize if known
        )

        # 1. Initial Enrichment via Discogs (Includes Swapped Search Fix)
        final = self._enrich_from_discogs(final)

        # 2. Enrichment via Spotify (Data Merge + Audio Features + Identity Fix)
        if self.spotify:
             should_run_spotify = True
             raw_artist = final.artist or ""
             raw_title = final.title or ""
             
             if not raw_title:
                 print("  -> [Enrichment] Imposible buscar en Spotify: Título vacío.")
                 should_run_spotify = False
             
             # Phase 22: Allow search even if Artist is empty (Free Search)
             # if not raw_artist... removed constraint
             
             if should_run_spotify:
                 # Phase 22: Free Search Fallback
                 # If artist is unknown/empty, we treat the Title as the full query (e.g. filename)
                 is_free_search = False
                 if not raw_artist or raw_artist in ["Unknown Artist", "Unknown"]:
                     print(f"  -> [Enrichment] Artista desconocido. Activando Free Search con Título: '{raw_title}'")
                     search_artist = ""
                     # Nuclear cleaning for title in free search is risky, better keep it broad or clean lightly
                     # For now, let's treat raw_title as the query directly
                     search_title = raw_title
                     is_free_search = True
                 else:
                     # Clean Artist as well (Fix for inverted files like Pilers where Artist has parens)
                     # "Pilers (Dela Remix)" -> "Pilers"
                     clean_artist = re.sub(r"\(.*?\)", "", raw_artist).strip()
                     search_artist = clean_artist.split(",")[0].split("&")[0].strip()
                     
                     # Phase 22: Nuclear Cleaning (Strip ALL parenthesis content)
                     # Fixes: "Brasilda (Back & Em Pi Remix)" -> "Brasilda"
                     search_title = re.sub(r"\(.*?\)", "", raw_title).strip() 
             
                 if is_free_search:
                     q1 = search_title
                     q2 = search_title # Redundant but keeps logic simple
                 else:
                     q1 = f"{search_artist} {search_title}"
                     q2 = f"{search_title} {search_artist}"
                 
                 print(f"  -> [Enrichment] Spotify Dual Query: '{q1}' / '{q2}'")
                 
                 res1 = self.spotify.search_broad(q1, search_artist, search_title)
                 res2 = self.spotify.search_broad(q2, search_artist, search_title)
                 
                 all_res = (res1 or []) + (res2 or [])
                 seen_ids = set()
                 unique_res = []
                 for t in all_res:
                     if t.id and t.id not in seen_ids:
                         unique_res.append(t)
                         seen_ids.add(t.id)
                 
                 unique_res.sort(key=lambda x: x.score, reverse=True)
                 
                 if unique_res:
                     best_s = unique_res[0]
                     if best_s.score > 0.10: 
                         print(f"  -> [Enrichment] Spotify Match: {best_s.title} - {best_s.album} ({best_s.year})")
                         
                         if not final.album and best_s.album:
                             final.album = best_s.album
                             print(f"     -> Recuperado Album: {final.album}")
                         if not final.year and best_s.year:
                             final.year = best_s.year
                             print(f"     -> Recuperado Año: {final.year}")
                         if not final.cover_url and best_s.cover_url:
                             final.cover_url = best_s.cover_url
                         
                         # PERSIST SPOTIFY ID (Phase 23 Fix)
                         final.spotify_id = best_s.id
                         final.spotify_url = best_s.url # Phase 24

                         # IDENTITY CORRECTION
                         # If Score > 0.6 OR it was a Free Search (Unknown Artist), we trust the result
                         should_correct_identity = (best_s.score > 0.6) or is_free_search
                         identity_changed = False
                         
                         if should_correct_identity: 
                             if final.artist != best_s.artist or final.title != best_s.title:
                                 final.title = best_s.title
                                 final.artist = best_s.artist
                                 identity_changed = True
                                 print(f"     -> Identidad Corregida: {final.artist} - {final.title}")

                         # LOOPBACK ENRICHMENT
                         if identity_changed and not final.label:
                             print("     -> [Fix] Identidad cambió. Re-ejecutando Discogs para buscar Editorial...")
                             final = self._enrich_from_discogs(final)
                             
                         # AUDIO FEATURES REMOVED (Phase 17)
                             
                     else:
                         print(f"  -> [Enrichment] Spotify Score insuficiente: {best_s.score:.2f}")

        # 3. Defaults
        if not final.genre:
            final.genre = 'Electronic'
            print("  -> [Enrichment] Asignando Género por defecto: Electronic")

        return final
