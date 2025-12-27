from __future__ import annotations

from typing import List, Dict, Any, Optional
import re


# ------------------------------------------------------
# HELPERS DE NORMALIZACIÓN
# ------------------------------------------------------
def _normalize(text: str) -> str:
    """Normaliza un texto para comparación sencilla."""
    text = text.lower()
    # Eliminar contenido entre paréntesis/brackets (versiones, mixes)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    # Quitar comillas raras
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    # Quitar guiones múltiples, etc.
    text = text.replace(" - ", " ")
    # Quitar espacios extra
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _similarity_basic(t1: Optional[str], t2: Optional[str]) -> float:
    """
    Similitud básica entre dos textos (0.0 a 1.0).
    Usa igualdad, substring y Jaccard de tokens.
    """
    if not t1 or not t2:
        return 0.0

    n1 = _normalize(t1)
    n2 = _normalize(t2)

    if not n1 or not n2:
        return 0.0

    if n1 == n2:
        return 1.0

    if n1 in n2 or n2 in n1:
        return 0.8

    s1 = set(n1.split())
    s2 = set(n2.split())
    if not s1 or not s2:
        return 0.0

    inter = s1.intersection(s2)
    union = s1.union(s2)
    if not union:
        return 0.0

    return len(inter) / len(union)


def _remix_keywords_score(tag_title: Optional[str], cand_title: Optional[str]) -> float:
    """
    Bonus si ambos títulos comparten "marcas DJ" (remix, extended, edit, club mix, etc.).
    Penalización suave si uno tiene muchas marcas y el otro no.
    """
    if not tag_title or not cand_title:
        return 0.0

    kw_list = [
        "remix",
        "extended",
        "club mix",
        "mix",
        "edit",
        "dub",
        "instrumental",
        "radio edit",
        "version",
        "bootleg",
    ]

    t_tag = _normalize(tag_title)
    t_cand = _normalize(cand_title)

    tag_hits = sum(1 for kw in kw_list if kw in t_tag)
    cand_hits = sum(1 for kw in kw_list if kw in t_cand)

    if tag_hits == 0 and cand_hits == 0:
        return 0.0

    if tag_hits > 0 and cand_hits > 0:
        # Ambos parecen “versiones DJ”
        return 0.5

    # Uno lo es y el otro no → ligera penalización
    return -0.2


def _similarity_title(tag_title: Optional[str], cand_title: Optional[str]) -> float:
    base = _similarity_basic(tag_title, cand_title)
    remix_bonus = _remix_keywords_score(tag_title, cand_title)
    return max(0.0, min(1.0, base + remix_bonus))


def _similarity_artist(tag_artist: Optional[str], cand_artist: Optional[str]) -> float:
    return _similarity_basic(tag_artist, cand_artist)


# ------------------------------------------------------
# SELECTOR PRINCIPAL
# ------------------------------------------------------
# ------------------------------------------------------
# SELECTOR PRINCIPAL
# ------------------------------------------------------
def select_best_acoustid_candidate(
    candidates: List[Dict[str, Any]],
    original_tags: Dict[str, Any],
    filename: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Selecciona el mejor candidato AcoustID.
    
    Validación mejorada:
    - Si hay tags ID3, compara con ellos.
    - Si NO hay tags ID3, intenta parsear el FILENAME (Artist - Title) y compara.
    - Si la similitud visual es muy baja (<0.2) y el score no es perfecto (1.0), penaliza severamente o descarta.
    """

    if not candidates:
        return None

    # 1. Extraer "Verdad Terreno" (Ground Truth) de tags o filename
    ref_title = None
    ref_artist = None

    # Intentar Tags
    if "TIT2" in original_tags:
        ref_title = str(original_tags["TIT2"])
    if "TPE1" in original_tags:
        ref_artist = str(original_tags["TPE1"])

    # Si faltan tags y tenemos filename, usar filename como fallback
    if (not ref_title or not ref_artist) and filename:
        # Importación local para evitar ciclos
        from mp3_autotagger.core.fallback import clean_filename
        
        clean_name = clean_filename(filename)
        # 1. Intentar " - " standard
        if " - " in clean_name:
            parts = clean_name.split(" - ", 1)
            if not ref_artist:
                ref_artist = parts[0].strip()
            if not ref_title:
                ref_title = parts[1].strip()
        # 2. Intentar "-" pegado si falla (riesgoso pero necesario para algunos files)
        elif "-" in clean_name:
             parts = clean_name.split("-", 1)
             if not ref_artist:
                ref_artist = parts[0].strip()
             if not ref_title:
                ref_title = parts[1].strip()
        else:
            if not ref_title:
                ref_title = clean_name
    
    # Debug info (Visible en consola para análisis)
    # print(f"[DEBUG Selection] Ref: '{ref_artist}' - '{ref_title}' (from tags/file)")

    def score_candidate(c: Dict[str, Any]) -> float:
        base_score = float(c.get("score") or 0.0)
        cand_title = c.get("title")
        cand_artist = c.get("artist")

        title_sim = _similarity_title(ref_title, cand_title)
        
        # Penalización por discrepancia masiva
        # Relaxed threshold: 0.1 -> 10% similarity required.
        # Solo aplicamos si TENEMOS referencia.
        penalty = 0.0
        if ref_title and title_sim < 0.1:
             # Si el título no se parece EN NADA (ni 10%), es sospechoso.
             # Pero si el score es SUPER alto (>0.95), confiamos un poco más (quizá remix con nombre distinto)
             # Antes era base_score < 1.0. Ahora relajamos a < 0.9
             if base_score < 0.90:
                 penalty = 0.5 
                 # print(f"  -> [REJECTED] '{cand_title}' vs Ref '{ref_title}' (Sim: {title_sim:.2f})")

        # Ponderación
        # 60% Audio Score, 30% Título, 10% Artista
        # Si Artista coincide, ayuda mucho.
        if ref_artist:
             artist_sim = _similarity_artist(ref_artist, cand_artist)
             total = 0.6 * base_score + 0.3 * title_sim + 0.1 * artist_sim
        else:
             # Si no tenemos artista ref, confiamos más en score y título
             total = 0.7 * base_score + 0.3 * title_sim
             
        total -= penalty
        
        return total

    # Ordenar candidatos por score descendente
    scored_candidates = []
    for c in candidates:
        s = score_candidate(c)
        scored_candidates.append((s, c))
    
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    best_score, best_cand = scored_candidates[0]
    
    # CRITERIO DE SEGURIDAD FINAL:
    # Si el mejor score calculado es muy bajo (< 0.4), rechazar todo.
    # Significa que o el audio es malo O el texto contradice al audio.
    if best_score < 0.4:
         # Loguear quizás?
         return None

    return best_cand
