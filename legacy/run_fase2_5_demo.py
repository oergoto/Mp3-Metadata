from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import List, Dict, Any, Optional

from fase1_identificacion.scanner import list_mp3_files
from fase1_identificacion.identify import (
    analyze_file,
    identify_with_acoustid,
    select_best_acoustid_candidate,
)
from fase1_identificacion.config import BASE_DIR
from fase2_musicbrainz.mb_client import MusicBrainzClient
from fase2_musicbrainz.models import TrackMetadataBase, MBRecording
from fase2_5_discogs.discogs_client import DiscogsClient
from fase2_5_discogs.matching import match_track_mb_to_discogs, DiscogsMatchResult


def build_track_metadata_for_file(
    file_path: str,
    mb_client: MusicBrainzClient,
) -> TrackMetadataBase:
    """
    Reconstruye un TrackMetadataBase para un archivo, usando:
    - analyze_file (Mutagen)
    - identify_with_acoustid + select_best_acoustid_candidate
    - MusicBrainzClient.get_recording

    Esta función replica la lógica conceptual de Fase 1 + Fase 2
    para un solo archivo.
    """
    base_info = analyze_file(file_path)
    duration = base_info.get("duration")
    tags = base_info.get("tags") or {}

    # 1. Llamar AcoustID
    candidates = identify_with_acoustid(file_path)
    best_cand = select_best_acoustid_candidate(candidates, duration_seconds=duration)

    acoustid_recording_id: Optional[str] = None
    acoustid_score: Optional[float] = None
    mb_recording: Optional[MBRecording] = None

    if best_cand is not None:
        acoustid_recording_id = best_cand["recording_id"]
        acoustid_score = best_cand["score"]

        # 2. Llamar MusicBrainz con el recording_id elegido
        if acoustid_recording_id:
            mb_recording = mb_client.get_recording(acoustid_recording_id)

    # 3. Construir TrackMetadataBase
    track_meta = TrackMetadataBase(
        file_path=file_path,
        duration_seconds=duration,
        original_tags=tags,
        acoustid_recording_id=acoustid_recording_id,
        acoustid_score=acoustid_score,
        mb_recording=mb_recording,
    )

    return track_meta


def ensure_results_dir() -> str:
    """
    Asegura que exista la carpeta de resultados:
    /Users/omarem4/Mp3 Metadata Music Library/Mp3 Metadata/resultados
    """
    results_dir = os.path.join(BASE_DIR, "resultados")
    os.makedirs(results_dir, exist_ok=True)
    return results_dir


def save_discogs_results_json(results: List[DiscogsMatchResult]) -> str:
    """
    Guarda la lista de DiscogsMatchResult en un archivo JSON
    con nombre tipo: YYYYMMDD-HH:MM:SS-resultados_fase2_5_discogs.json
    dentro de la carpeta 'resultados'.
    """
    results_dir = ensure_results_dir()
    timestamp = datetime.now().strftime("%Y%m%d-%H:%M:%S")
    filename = f"{timestamp}-resultados_fase2_5_discogs.json"
    path = os.path.join(results_dir, filename)

    data: List[Dict[str, Any]] = [asdict(r) for r in results]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path


def run_demo(limit_files: int = 10) -> None:
    """
    Demo de Fase 2.5:
    - Toma 'limit_files' MP3 de la carpeta RAW.
    - Reconstruye TrackMetadataBase (AcoustID + MusicBrainz).
    - Llama Discogs matching.
    - Imprime resumen en consola.
    - Exporta JSON con resultados.
    """
    print("=== DEMO FASE 2.5 – MUSICBRAINZ → DISCOGS (MATCHING) ===")

    # 1. Listar archivos MP3 desde la carpeta RAW
    mp3_files = list_mp3_files(limit=limit_files)
    if not mp3_files:
        print("No se encontraron archivos MP3 en la carpeta RAW.")
        return

    print(f"Procesando hasta {len(mp3_files)} archivos...\n")

    # 2. Instanciar clientes
    mb_client = MusicBrainzClient()
    discogs_client = DiscogsClient()

    results: List[DiscogsMatchResult] = []

    for idx, file_path in enumerate(mp3_files, start=1):
        print("\n" + "=" * 60)
        print(f"[{idx:02d}] Archivo: {file_path}")

        # Reconstruir metadatos base (incluye AcoustID + MB)
        track_meta = build_track_metadata_for_file(file_path, mb_client=mb_client)

        mb_title = track_meta.main_title() or "(sin título MB)"
        mb_artist = track_meta.main_artist_name() or "(sin artista MB)"

        print(f"  MB title : {mb_title}")
        print(f"  MB artist: {mb_artist}")

        if track_meta.acoustid_recording_id is None:
            print("  → No hay recording_id de AcoustID/MusicBrainz. Se saltará Discogs (SIN_MATCH_DISCOGS).")
            match_result = DiscogsMatchResult(
                file_path=file_path,
                mb_recording_id=None,
                mb_release_id=None,
                mb_title=track_meta.main_title(),
                mb_artist=track_meta.main_artist_name(),
                mb_release_title=None,
                mb_release_date=None,
                discogs_release_id=None,
                discogs_master_id=None,
                discogs_title=None,
                discogs_artist=None,
                discogs_year=None,
                discogs_country=None,
                discogs_label=None,
                discogs_catno=None,
                discogs_confidence_label="SIN_MATCH_DISCOGS",
                discogs_confidence_score=0.0,
            )
            results.append(match_result)
            continue

        # 3. Matching con Discogs
        match_result = match_track_mb_to_discogs(track_meta, discogs_client)
        results.append(match_result)

        # 4. Mostrar resumen por pista
        print(f"  Discogs confianza : {match_result.discogs_confidence_label} "
              f"({match_result.discogs_confidence_score:.3f})")

        if match_result.discogs_release_id:
            print(f"  Discogs release id: {match_result.discogs_release_id}")
            print(f"  Discogs title     : {match_result.discogs_title}")
            print(f"  Discogs artist    : {match_result.discogs_artist}")
            print(f"  Discogs year      : {match_result.discogs_year}")
            print(f"  Discogs country   : {match_result.discogs_country}")
            print(f"  Discogs label     : {match_result.discogs_label}")
            print(f"  Discogs catno     : {match_result.discogs_catno}")
        else:
            print("  → SIN_MATCH_DISCOGS (no se seleccionó ningún release).")

    # 5. Guardar resultados en JSON
    output_path = save_discogs_results_json(results)
    print("\n=== DEMO COMPLETADA ===")
    print(f"Resultados guardados en: {output_path}")


if __name__ == "__main__":
    # Por defecto procesa 10 archivos. Puedes ajustar si quieres.
    run_demo(limit_files=30)
