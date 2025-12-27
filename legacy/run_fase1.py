from __future__ import annotations

import os

from fase1_identificacion.scanner import list_mp3_files
from fase1_identificacion.identify import analyze_file, identify_with_acoustid
from fase1_identificacion.selection import select_best_acoustid_candidate
from fase1_identificacion.results_export import (
    TrackAnalysisResult,
    classify_confidence,
    export_results,
)

from fase2_musicbrainz.mb_client import MusicBrainzClient
from fase2_musicbrainz.models import TrackMetadataBase


def main() -> None:
    """
    Pipeline integrado Fase 1 + Fase 2 para hasta 20 tracks:

    1. Lista archivos MP3 en Music-Library-RAW.
    2. Extrae duración y tags base (Mutagen).
    3. Identifica con AcoustID (fingerprint).
    4. Usa select_best_acoustid_candidate para elegir el mejor candidato.
    5. Consulta MusicBrainz para ese recording_id.
    6. Construye TrackMetadataBase.
    7. Clasifica nivel de confianza.
    8. Acumula resultados y los exporta en JSON/CSV.
    """

    # Procesamos hasta 20 archivos
    mp3_files = list_mp3_files(limit=20)
    if not mp3_files:
        print("No se encontraron archivos MP3 en la carpeta RAW.")
        return

    mb_client = MusicBrainzClient()

    resultados: list[TrackAnalysisResult] = []

    for path in mp3_files:
        print("\n==============================")
        print("Archivo:", path)

        # 1) Info base del archivo (duración + tags actuales)
        base_info = analyze_file(path)
        duration = base_info["duration"]
        tags = base_info["tags"]

        print("Duración aproximada:", duration)
        print("Tags base:", tags)

        # 2) Identificación acústica con AcoustID
        candidates = identify_with_acoustid(path)

        if not candidates:
            print("Sin coincidencias en AcoustID por encima del umbral configurado.")

            track_meta = TrackMetadataBase(
                file_path=path,
                duration_seconds=duration,
                original_tags=tags,
                acoustid_recording_id=None,
                acoustid_score=None,
                mb_recording=None,
            )
            conf_label, conf_score = "SIN_MATCH", 0.0

            resultados.append(
                TrackAnalysisResult(
                    file_path=path,
                    duration_seconds=duration,
                    original_title_tag=str(tags.get("TIT2")) if tags.get("TIT2") else None,
                    original_artist_tag=str(tags.get("TPE1")) if tags.get("TPE1") else None,
                    acoustid_score=None,
                    acoustid_recording_id=None,
                    mb_title=None,
                    mb_artist=None,
                    best_release_title=None,
                    best_release_date=None,
                    best_release_country=None,
                    best_release_status=None,
                    confidence_label=conf_label,
                    confidence_score=conf_score,
                )
            )
            continue

        print(f"Candidatos AcoustID/MusicBrainz (total {len(candidates)}):")
        for idx, c in enumerate(candidates, start=1):
            score = c["score"]
            artist = c.get("artist") or "Desconocido"
            title = c.get("title") or "Sin título"
            rec_id = c["recording_id"]
            print(
                f"  {idx:02d}. score={score:.3f} | artista={artist} | "
                f"título={title} | recording_id={rec_id}"
            )

        # 3) Elegimos el mejor candidato usando también las tags locales
        best = select_best_acoustid_candidate(candidates, tags)
        if not best:
            print("No se pudo seleccionar un candidato óptimo de AcoustID.")
            continue

        best_score = best["score"]
        best_rec_id = best["recording_id"]

        print("\n  → Mejor candidato AcoustID sugerido (con helper):")
        print(
            f"     score={best_score:.3f} | artista={best.get('artist') or 'Desconocido'} | "
            f"título={best.get('title') or 'Sin título'} | recording_id={best_rec_id}"
        )

        # 4) Enriquecimiento con MusicBrainz usando el recording_id del mejor candidato
        mb_rec = mb_client.get_recording(best_rec_id)
        if not mb_rec:
            print("No se pudo obtener información de MusicBrainz para el recording_id seleccionado.")
            continue

        # 5) Construimos TrackMetadataBase con toda la info disponible
        track_meta = TrackMetadataBase(
            file_path=path,
            duration_seconds=duration,
            original_tags=tags,
            acoustid_recording_id=best_rec_id,
            acoustid_score=best_score,
            mb_recording=mb_rec,
        )

        print("\n--- Metadatos enriquecidos (MusicBrainz) ---")
        print("Título (MB):", track_meta.main_title())
        print("Artista principal (MB):", track_meta.main_artist_name())

        best_release = track_meta.best_release()
        if best_release:
            print("\nRelease sugerido (heurística DJ):")
            print(" - Título:", best_release.title)
            print(" - Fecha:", best_release.date)
            print(" - País:", best_release.country)
            print(" - Status:", best_release.status)
        else:
            print("\nNo se pudo determinar un release sugerido para este recording.")

        # 6) Clasificamos confianza
        conf_label, conf_score = classify_confidence(track_meta)
        print(f"\nNivel de confianza: {conf_label} (score compuesto={conf_score:.3f})")

        # Datos para exportar
        mb_title = track_meta.main_title()
        mb_artist = track_meta.main_artist_name()

        br_title = best_release.title if best_release else None
        br_date = best_release.date if best_release else None
        br_country = best_release.country if best_release else None
        br_status = best_release.status if best_release else None

        resultados.append(
            TrackAnalysisResult(
                file_path=path,
                duration_seconds=duration,
                original_title_tag=str(tags.get("TIT2")) if tags.get("TIT2") else None,
                original_artist_tag=str(tags.get("TPE1")) if tags.get("TPE1") else None,
                acoustid_score=best_score,
                acoustid_recording_id=best_rec_id,
                mb_title=mb_title,
                mb_artist=mb_artist,
                best_release_title=br_title,
                best_release_date=br_date,
                best_release_country=br_country,
                best_release_status=br_status,
                confidence_label=conf_label,
                confidence_score=conf_score,
            )
        )

    # 7) Exportamos resultados al final del procesamiento
    # BASE_DIR del proyecto (carpeta Mp3 Metadata)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)

    export_results(resultados, base_dir=project_root)


if __name__ == "__main__":
    main()
