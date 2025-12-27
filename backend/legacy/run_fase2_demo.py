from fase2_musicbrainz.mb_client import MusicBrainzClient
from fase2_musicbrainz.models import TrackMetadataBase


def demo_from_recording_id(file_path: str, recording_id: str, score: float) -> None:
    client = MusicBrainzClient()

    print("\n=== DEMO FASE 2 – MUSICBRAINZ ===")
    print("Archivo base:", file_path)
    print("Recording ID (AcoustID/MB):", recording_id)
    print("Score AcoustID:", score)

    mb_rec = client.get_recording(recording_id)
    if not mb_rec:
        print("No se pudo obtener información de MusicBrainz para ese recording_id.")
        return

    track_meta = TrackMetadataBase(
        file_path=file_path,
        acoustid_recording_id=recording_id,
        acoustid_score=score,
        mb_recording=mb_rec,
    )

    print("\nTítulo (MB):", track_meta.main_title())
    print("Artista principal (MB):", track_meta.main_artist_name())

    best_rel = track_meta.best_release()
    if best_rel:
        print("\nRelease sugerido (simple heurística):")
        print(" - Título:", best_rel.title)
        print(" - Fecha:", best_rel.date)
        print(" - País:", best_rel.country)
        print(" - Status:", best_rel.status)
    else:
        print("\nNo se encontraron releases asociados en MusicBrainz.")


if __name__ == "__main__":
    # Usa uno de los recording_id reales detectados en Fase 1
    example_file = "/Users/omarem4/Mi unidad (oergoto@gmail.com)/PROYECTOS/Mp3 Metadata Music Library/Music-Library-RAW/03. Kylie Minogue - Can't Get Blue Monday Out Of My Head (Original 12'' Mix).mp3"
    example_recording_id = "48ab5ae5-10c3-4b0b-8e3e-ea33e507e411"
    example_score = 0.989

    demo_from_recording_id(example_file, example_recording_id, example_score)
