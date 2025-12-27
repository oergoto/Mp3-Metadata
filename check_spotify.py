
from mp3_autotagger.clients.spotify import SpotifyClient
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_spotify():
    client = SpotifyClient()
    
    artist = "Afro Medusa"
    title = "Pasilda"
    
    print(f"--- Spotify Test: {artist} - {title} ---")
    
    # 1. Search
    tracks = client.search_track(artist, title)
    
    if not tracks:
        print("No tracks found.")
        return

    print(f"Found {len(tracks)} tracks.")
    
    best_track = tracks[0]
    print(f"Top Match: {best_track.title} by {best_track.artist}")
    print(f"Album: {best_track.album} ({best_track.year})")
    print(f"Spotify ID: {best_track.id}")
    print(f"Score: {best_track.score:.2f}")
    
    if best_track.id:
        # 2. Audio Features
        print(f"\n--- Audio Features for {best_track.id} ---")
        features = client.get_audio_features(best_track.id)
        if features:
            print(f"BPM: {features.get('tempo')}")
            print(f"Key: {features.get('key')} (Mode: {features.get('mode')})")
            print(f"Danceability: {features.get('danceability')}")
            print(f"Energy: {features.get('energy')}")
        else:
            print("No audio features found.")

if __name__ == "__main__":
    test_spotify()
