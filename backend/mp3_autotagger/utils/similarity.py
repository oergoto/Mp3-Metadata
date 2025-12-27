from fuzzywuzzy import fuzz

def calculate_similarity_score(search_artist: str, search_title: str, track_artist: str, track_title: str) -> float:
    """
    Calculate a similarity score between search terms and track metadata.
    Returns a float between 0.0 and 1.0.
    """
    search_str = f"{search_artist} {search_title}".lower()
    track_str = f"{track_artist} {track_title}".lower()
    
    # Use token_set_ratio to handle word reordering and partial matches
    try:
        score = fuzz.token_set_ratio(search_str, track_str)
        return score / 100.0
    except ImportError:
        # Fallback if libraries are missing (unlikely given env)
        import difflib
        return difflib.SequenceMatcher(None, search_str, track_str).ratio()
