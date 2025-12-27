import os
from typing import List

RAW_DIR = "/Users/omarem4/Mi unidad (oergoto@gmail.com)/PROYECTOS/Mp3 Metadata Music Library/Music-Library-RAW"  # Ajustar si la ruta final difiere


def list_mp3_files(limit: int | None = None) -> List[str]:
    """Lista archivos .mp3 en la carpeta RAW (sin recursividad para Fase 1)."""
    files: List[str] = []
    for entry in os.listdir(RAW_DIR):
        full_path = os.path.join(RAW_DIR, entry)
        if os.path.isfile(full_path) and entry.lower().endswith(".mp3"):
            files.append(full_path)
    files.sort()
    if limit is not None:
        return files[:limit]
    return files


if __name__ == "__main__":
    mp3_files = list_mp3_files(limit=20)
    print("Archivos encontrados:")
    for f in mp3_files:
        print(" -", f)