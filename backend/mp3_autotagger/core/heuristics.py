from typing import List, Optional, Tuple

class ReleaseHeuristics:
    """
    Lógica de decisión para seleccionar el mejor Release de MusicBrainz.
    Separada de los modelos de datos para mantener el principio de responsabilidad única.
    """
    
    COMPILATION_PATTERNS = [
        "best of",
        "greatest hits",
        "the very best",
        "dance anthems",
        "hits of",
        "mega hits",
        "collection",
        "collections",
        "anthology",
        "various artists",
    ]

    @staticmethod
    def looks_like_compilation(title: str) -> bool:
        """Determina si un título parece ser de un compilatorio."""
        if not title:
            return False
        t = title.lower()
        return any(pat in t for pat in ReleaseHeuristics.COMPILATION_PATTERNS)

    @staticmethod
    def score_release(release, recording_title: Optional[str] = None) -> Tuple[int, int, int, str]:
        """
        Calcula un score para ordenar releases.
        Devuelve una tupla para usar en sort/min/max.
        
        Criterios (en orden de prioridad):
        1. Oficial (-1 = Official, 0 = Otros)
        2. Coincidencia de Título (-1 = Match, 0 = No Match)
        3. No Compilatorio (0 = Normal, 1 = Compilatorio)
        4. Fecha (YYYY-MM-DD, más antiguo primero)
        """
        # 1. Official
        status = (release.status or "").lower()
        is_official = 0 if status == "official" else 1 # Para sort ascendente (menor es mejor): -1 es complicado si no usamos ints.
        # Mejor lógica "Menor es mejor":
        # - Official -> 0, Otros -> 1
        score_official = 0 if status == "official" else 1

        # 2. Coincidencia de títulos
        # Queremos priorizar coincidencia. Match -> 0, No Match -> 1
        score_title_match = 1
        rel_title = (release.title or "").lower().strip()
        rec_title = (recording_title or "").lower().strip()
        
        if rec_title and rel_title:
            if rec_title in rel_title or rel_title in rec_title:
                score_title_match = 0

        # 3. Penalización compilatorios
        # No Compilacion -> 0, Compilacion -> 1
        is_compilation = 1 if ReleaseHeuristics.looks_like_compilation(rel_title) else 0

        # 4. Fecha
        # String comparison works for ISO dates: "1999" < "2000". We want older first.
        # "1999" es menor que "2000", así que sort ascendente funciona.
        date_str = release.date or ""
        date_key = date_str if date_str else "9999-99-99"

        return (score_official, score_title_match, is_compilation, date_key)
