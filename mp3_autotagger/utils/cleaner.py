import re
import os

class FilenameCleaner:
    """
    Utility to clean filenames from common DJ/Rip noise before searching.
    Removes:
    - 'Unknown Artist'
    - Camelot/BPM prefixes (e.g. '2A - 125 - ')
    - Track numbers (e.g. '01 - ')
    - Web garbage (e.g. 'www.mp3...')
    """

    @staticmethod
    def clean(filename: str) -> str:
        # 1. Base Cleanup of known garbage strings
        garbage = [
            "Unknown Artist",
            "Unknown Artist -", 
            "www.mp3", 
            "Youtube Rip",
            "y2mate.com",
            "y2mate",
            "www.youtube.com",
            "_320kbps",
            "320kbps",
            "(Original Mix)", # Optional: User didn't strictly ask to remove this but it helps search. 
                              # Actually user example 'Munbo Gumbo (Original Mix)' kept it in title, 
                              # but for SEARCH it might be better to keep or remove?
                              # User code sample: `basura = ["Unknown Artist", ...]`
                              # I will stick to the user's explicit list + obvious functional noise.
        ]
        
        cleaned = os.path.basename(filename)
        # Remove extension for processing
        name, ext = os.path.splitext(cleaned)
        cleaned = name

        for g in garbage:
            cleaned = cleaned.replace(g, "")

        # 2. Regex Cleanup for Prefixes
        
        # Camelot Key + BPM: "2A - 125 - " or "2A - 125 "
        # Pattern: Start of string, 1-2 digits, 1 letter, optionally ' - ', 2-3 digits, optionally ' - '
        # Regex: ^\d{1,2}[A-Z]\s+-\s+\d{2,3}\s+-\s+
        cleaned = re.sub(r'^\d{1,2}[A-Z]\s+-\s+\d{2,3}\s+-\s+', '', cleaned)
        
        # Simple Camelot: "2A - "
        cleaned = re.sub(r'^\d{1,2}[A-Z]\s+-\s+', '', cleaned)

        # Track Numbers: "01 - " or "01. "
        cleaned = re.sub(r'^\d{2,3}\s*[-.]\s+', '', cleaned)

        # 3. Final Polish
        cleaned = cleaned.replace("_", " ").strip()
        cleaned = re.sub(r'\s+', ' ', cleaned) # Collapse multiple spaces
        
        # Remove explicit " - " at start if it remains
        if cleaned.startswith("- "):
            cleaned = cleaned[2:].strip()

        return cleaned

    @staticmethod
    def extract_artist_title(cleaned_filename: str):
        """
        Attempts to split Artist - Title.
        Returns (artist, title) or (None, cleaned_filename) if no split found.
        """
        if " - " in cleaned_filename:
            parts = cleaned_filename.split(" - ", 1)
            return parts[0].strip(), parts[1].strip()
        return None, cleaned_filename
