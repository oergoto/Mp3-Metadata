import sys
import os

# Ensure package is in path (Parent of this script)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp3_autotagger.core.pipeline import PipelineCore
from mp3_autotagger.core.tagger import Tagger

def test_pipeline(file_path):
    print(f"Testing Unified Pipeline on: {file_path}")
    
    pipeline = PipelineCore(use_discogs=True, use_spotify=True)
    
    try:
        result = pipeline.process_file(file_path)
        print("\n--- Pipeline Result ---")
        unified = result.track_metadata
        print(f"Title: {unified.title}")
        print(f"Artist: {unified.artist_main}")
        print(f"Album: {unified.album}")
        print(f"Year: {unified.year}")
        print(f"Genre: {unified.genre_main}")
        print(f"Catalog: {unified.editorial.catalog_number}")
        print(f"MB Track ID: {unified.ids.musicbrainz_track_id}")
        
        print("\n--- Testing Tagger (Dry Run) ---")
        tagger = Tagger(dry_run=True)
        tagger.write_metadata(unified)
        
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Hardcoded test path based on history, or first arg
    test_file = "/Users/omarem4/Mi unidad (oergoto@gmail.com)/PROYECTOS/Mp3 Metadata Music Library/Mp3 Metadata/Tanghetto/El Miedo a la Libertad/04 - Tanghetto - Vida Moderna.mp3"
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        
    if not os.path.exists(test_file):
        print(f"File not found: {test_file}")
        # Try to find one
        print("Searching for an mp3...")
        import glob
        files = glob.glob("/Users/omarem4/Mi unidad (oergoto@gmail.com)/PROYECTOS/Mp3 Metadata Music Library/Mp3 Metadata/**/*.mp3", recursive=True)
        if files:
            test_file = files[0]
            print(f"Found: {test_file}")
            test_pipeline(test_file)
        else:
             print("No MP3s found to test.")
    else:
        test_pipeline(test_file)
