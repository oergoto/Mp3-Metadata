from __future__ import annotations

import os
import json
import csv
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import re

from fase2_musicbrainz.models import TrackMetadataBase, MBRelease


# ------------------------------------------------------
# NORMALIZACIÓN Y SIMILITUD
# ------------------------------------------------------
def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _similarity_basic(t1: Optional[str], t2: Optional[str]) -> float:
    if not t1 or not t2:
        return 0.0

    n1 = _normalize(t1)
    n2 = _normalize(t2)

    if n1 == n2:
        return 1.0

    if n1 in n2 or n2 in n1:
        return 0.8

    set1 = set(n1.split())
    set2 = set(n2.split())
    if not set1 or not set2:
        return 0.0

    inter = set1.intersection(set2)
    union = set1.union(set2)
    return len(inter) / len(union) if union else 0.0


def _remix_keywords_score(tag_title: Optional[str], cand_title: Optional[str]) -> float:
    if not tag_title or not cand_title:
        return 0.0

    kw = [
        "remix", "extended", "club mix", "edit", "mix", "dub",
        "instrumental", "radio edit", "bootleg", "version"
    ]

    t1 = _normalize(tag_title)
    t2 = _normalize(cand_title)

    tag_hits = sum(1 for k in kw if k in t1)
    cand_hits = sum(1 for k in kw if k in t2)

    if tag_hits > 0 and cand_hits > 0:
        return 0.5
    if (tag_hits > 0 and cand_hits == 0) or (tag_hits == 0 and cand_hits > 0):
        return -0.2
    return 0.0


def _similarity_title(tag_title: Optional[str], cand_title: Optional[str]) -> float:
    base = _similarity_basic(tag_title, cand_title)
    bonus = _remix_keywords_score(tag_title, cand_title)
    return max(0.0, min(1.0, base + bonus))


def _similarity_artist(tag_artist: Optional[str], cand_artist: Optional[str]) -> float:
    return _similarity_basic(tag_artist, cand_artist)


# ------------------------------------------------------
# OUTPUT DEL PIPELINE
# ------------------------------------------------------
@dataclass
class TrackAnalysisResult:
    file_path: str

    duration_seconds: Optional[float]
    original_title_tag: Optional[str]
    original_artist_tag: Optional[str]

    acoustid_score: Optional[float]
    acoustid_recording_id: Optional[str]

    mb_title: Optional[str]
    mb_artist: Optional[str]

    best_release_title: Optional[str]
    best_release_date: Optional[str]
    best_release_country: Optional[str]
    best_release_status: Optional[str]

    confidence_label: str
    confidence_score: float


# ------------------------------------------------------
# CLASIFICADOR DE CONFIANZA
# ------------------------------------------------------
def classify_confidence(track_meta: TrackMetadataBase) -> (str, float):
    if track_meta.mb_recording is None or track_meta.acoustid_recording_id is None:
        return "SIN_MATCH", 0.0

    score_ac = track_meta.acoustid_score or 0.0

    tags = track_meta.original_tags or {}
    tag_title = str(tags.get("TIT2")) if tags.get("TIT2") else None
    tag_artist = str(tags.get("TPE1")) if tags.get("TPE1") else None

    mb_title = track_meta.main_title()
    mb_artist = track_meta.main_artist_name()

    sim_title = _similarity_title(tag_title, mb_title)
    sim_artist = _similarity_artist(tag_artist, mb_artist)

    total = score_ac + 0.15 * sim_title + 0.15 * sim_artist

    if score_ac >= 0.97 and sim_title >= 0.7 and sim_artist >= 0.7:
        label = "CONF_AUTO_ALTA"
    elif score_ac >= 0.94 and sim_title >= 0.5 and sim_artist >= 0.5:
        label = "CONF_AUTO_MEDIA"
    else:
        label = "REVISAR_MANUAL"

    return label, float(total)


# ------------------------------------------------------
# EXPORTACIÓN JSON / CSV A CARPETA “resultados”
# ------------------------------------------------------
def export_results(
    results: List[TrackAnalysisResult],
    base_dir: str,
    base_name: str = "resultados_fase1_fase2",
) -> None:
    if not results:
        print("No hay resultados para exportar.")
        return

    # Carpeta final
    output_dir = os.path.join(base_dir, "resultados")
    os.makedirs(output_dir, exist_ok=True)

    # Timestamp YYYYMMDD-HH:MM:SS
    timestamp = datetime.now().strftime("%Y%m%d-%H:%M:%S")

    json_filename = f"{timestamp}-{base_name}.json"
    csv_filename = f"{timestamp}-{base_name}.csv"

    json_path = os.path.join(output_dir, json_filename)
    csv_path = os.path.join(output_dir, csv_filename)

    # JSON
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump([asdict(r) for r in results], f_json, ensure_ascii=False, indent=2)

    # CSV
    fieldnames = list(asdict(results[0]).keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    print("\n=== EXPORTACIÓN COMPLETADA ===")
    print("JSON:", json_path)
    print("CSV :", csv_path)
