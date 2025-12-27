from __future__ import annotations

from typing import Any, Dict, List, Optional

import acoustid
from mutagen import File as MutagenFile

from mp3_autotagger.config import ACOUSTID_API_KEY


def analyze_file(path: str) -> Dict[str, Any]:
    """
    Extrae duración aproximada y tags básicos usando Mutagen.

    Retorna un diccionario con:
      - duration: duración en segundos (float o None)
      - tags: dict con algunos campos ID3 básicos (cuando existan)
    """
    audio = MutagenFile(path)
    if not audio or not audio.info:
        return {"duration": None, "tags": {}}

    duration = getattr(audio.info, "length", None)

    tags: Dict[str, Any] = {}
    if audio.tags:
        # Campos ID3 típicos en MP3
        for key in ("TIT2", "TPE1", "TALB", "TCON"):
            if key in audio.tags:
                try:
                    tags[key] = str(audio.tags[key])
                except Exception:
                    tags[key] = audio.tags[key].text if hasattr(audio.tags[key], "text") else str(
                        audio.tags[key]
                    )

    return {"duration": duration, "tags": tags}


def identify_with_acoustid(path: str) -> List[Dict[str, Any]]:
    """
    Genera fingerprint y consulta AcoustID, devolviendo candidatos MusicBrainz.

    Cada candidato es un dict con:
      - score: float
      - recording_id: str (MBID de recording en MusicBrainz)
      - title: str | None
      - artist: str | None
    """
    results: List[Dict[str, Any]] = []
    try:
        for score, recording_id, title, artist in acoustid.match(ACOUSTID_API_KEY, path):
            results.append(
                {
                    "score": float(score),
                    "recording_id": recording_id,
                    "title": title,
                    "artist": artist,
                }
            )
    except acoustid.AcoustidError as e:
        print(f"Error en AcoustID para {path}: {e}")
    return results


def select_best_acoustid_candidate(
    candidates: List[Dict[str, Any]],
    duration_seconds: Optional[float] = None,
    min_score: float = 0.70,
) -> Optional[Dict[str, Any]]:
    """
    Selecciona el mejor candidato de AcoustID de forma robusta.

    Parámetros:
      - candidates: lista de dicts devueltos por identify_with_acoustid().
      - duration_seconds: duración aproximada del archivo (Mutagen).
                          Por ahora solo se usa como referencia, pero se puede
                          extender para hacer filtros de duración si es necesario.
      - min_score: umbral mínimo de score para aceptar el match.

    Regresa:
      - dict del mejor candidato (score más alto) si cumple el umbral.
      - None si no hay candidatos o el mejor no alcanza min_score.
    """
    if not candidates:
        return None

    # Elegimos el de mayor score
    best = max(candidates, key=lambda c: c.get("score", 0.0))
    best_score = float(best.get("score", 0.0))

    # En esta versión no filtramos por duración por falta de info de duración por candidato,
    # pero dejamos el parámetro para futuras mejoras.
    # Si el score es bajo, no lo consideramos suficientemente confiable.
    if best_score < min_score:
        return None

    return best


if __name__ == "__main__":
    # Pequeña prueba manual (ajusta la ruta antes de usar)
    test_path = "/Users/omarem4/Mi unidad (oergoto@gmail.com)/PROYECTOS/Mp3 Metadata Music Library/Music-Library-RAW/01. F.R.E.A.K (Original Mix).mp3"

    print("Probando analyze_file()...")
    info = analyze_file(test_path)
    print("Duración:", info["duration"])
    print("Tags   :", info["tags"])

    print("\nProbando identify_with_acoustid()...")
    cands = identify_with_acoustid(test_path)
    for c in cands:
        print(
            f"  score={c['score']:.3f} | artist={c['artist']} | title={c['title']} | rec_id={c['recording_id']}"
        )

    print("\nProbando select_best_acoustid_candidate()...")
    best = select_best_acoustid_candidate(cands, duration_seconds=info["duration"])
    print("Mejor candidato:", best)
