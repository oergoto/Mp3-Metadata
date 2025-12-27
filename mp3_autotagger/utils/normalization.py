from __future__ import annotations

import re
import unicodedata
from typing import List, Set, Tuple, Optional


# ============================================================
# Utilidades básicas de normalización de texto
# ============================================================

def _to_str(s: Optional[str]) -> str:
    return "" if s is None else str(s)


def normalize_whitespace(text: str) -> str:
    """
    Colapsa espacios en blanco múltiples en uno solo
    y recorta al inicio y al final.
    """
    text = _to_str(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_unicode(text: str) -> str:
    """
    Normaliza a forma NFC y reemplaza algunos caracteres especiales
    comunes en fuentes musicales (comillas curvas, etc.).
    """
    text = _to_str(text)
    text = unicodedata.normalize("NFC", text)
    # Reemplazos de comillas “tontas”
    text = text.replace("’", "'").replace("`", "'")
    text = text.replace("“", '"').replace("”", '"')
    return text


def remove_accents(text: str) -> str:
    """
    Elimina acentos y diacríticos, convirtiendo a ASCII aproximado.
    Ej: 'Sébastien' -> 'Sebastien'
    """
    text = _to_str(text)
    nfkd_form = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def strip_brackets(text: str) -> str:
    """
    Elimina el contenido entre paréntesis () y brackets [].
    Ejemplo:
        'Lady (Hear Me Tonight) [Extended Mix]' -> 'Lady'
    """
    text = _to_str(text)
    # Primero quitar contenido [entre corchetes]
    text = re.sub(r"\[.*?\]", "", text)
    # Luego quitar contenido (entre paréntesis)
    text = re.sub(r"\(.*?\)", "", text)
    return normalize_whitespace(text)


def collapse_acronyms(text: str) -> str:
    """
    Colapsa acrónimos con puntos (F.R.E.A.K -> FREAK).
    """
    text = _to_str(text)
    # Reemplazar puntos entre letras por nada: "F.R.E." -> "FRE"
    # Solo si hay al menos 2 letras con puntos
    return re.sub(r"([a-zA-Z])\.([a-zA-Z])", r"\1\2", text)


def basic_normalize(text: str) -> str:
    """
    Normalización básica para comparaciones:
    - unicode normalizado
    - minúsculas
    - quita brackets/paréntesis
    - colapsa acrónimos (F.R.E.A.K -> FREAK)
    - colapsa espacios
    """
    text = normalize_unicode(text)
    text = text.lower()
    text = strip_brackets(text)
    text = collapse_acronyms(text)
    text = normalize_whitespace(text)
    return text


# ============================================================
# Normalización específica de ARTISTAS
# ============================================================

_FEAT_PATTERNS = [
    r"\s+feat\.?\s+",
    r"\s+ft\.?\s+",
    r"\s+featuring\s+",
]


def split_artist_main_and_feat(artist: str) -> Tuple[str, List[str]]:
    """
    Divide una cadena de artista en:
    - nombre principal
    - lista de artistas 'feat/ft/featuring' si se pueden detectar.

    Ejemplo:
        'Artist feat. Singer & Rapper' ->
            main = 'Artist'
            feats = ['Singer & Rapper']
    """
    artist = normalize_unicode(artist)
    artist = normalize_whitespace(artist)

    # Intentar cortar por el primer patrón de "feat"
    for pat in _FEAT_PATTERNS:
        m = re.search(pat, artist, flags=re.IGNORECASE)
        if m:
            main = artist[: m.start()].strip()
            rest = artist[m.end() :].strip()
            feats = [rest] if rest else []
            return main, feats

    # Si no hay feat, todo es main
    return artist, []


def normalize_artist_name(artist: str) -> str:
    """
    Devuelve una versión normalizada del nombre del artista para comparaciones.
    - unicode normalizado
    - minúsculas
    - espacios colapsados
    - se quita el bloque 'feat./ft./featuring ...' para el main
    """
    main, _ = split_artist_main_and_feat(artist)
    return basic_normalize(main)


# ============================================================
# Normalización específica de TÍTULOS
# ============================================================

_REMIX_KEYWORDS = [
    "remix",
    "extended",
    "club mix",
    "mix",
    "edit",
    "version",
    "dub",
    "radio edit",
    "instrumental",
    "bootleg",
]


def extract_title_base_and_suffix(title: str) -> Tuple[str, str]:
    """
    Separa un título en:
    - base (sin paréntesis/brackets)
    - sufijo (el contenido que suele indicar versión / remix)

    Ejemplo:
        'Praise You (Purple Disco Machine Extended Remix)'
        -> base='Praise You'
           suffix='Purple Disco Machine Extended Remix'
    """
    title = normalize_unicode(title)
    title = normalize_whitespace(title)

    # Extraer contenido entre paréntesis y brackets como sufijo
    suffix_parts: List[str] = []

    def _collect(pattern: str, text: str) -> Tuple[str, List[str]]:
        parts: List[str] = []
        def repl(m: re.Match) -> str:
            inner = m.group(1).strip()
            if inner:
                parts.append(inner)
            return ""
        new_text = re.sub(pattern, repl, text)
        return new_text, parts

    # () primero
    title_no_parens, paren_parts = _collect(r"\((.*?)\)", title)
    # [] después
    title_no_brackets, bracket_parts = _collect(r"\[(.*?)\]", title_no_parens)

    suffix_parts.extend(paren_parts)
    suffix_parts.extend(bracket_parts)

    base = normalize_whitespace(title_no_brackets)
    suffix = " ".join(suffix_parts)
    suffix = normalize_whitespace(suffix)
    return base, suffix


def normalize_title_for_search(title: str) -> str:
    """
    Normaliza título para búsquedas base:
    - quita sufijos de versión/remix entre () y []
    - minúsculas, unicode normalizado, espacios colapsados.
    """
    base, _ = extract_title_base_and_suffix(title)
    return basic_normalize(base)


def detect_mix_keywords(text: str) -> List[str]:
    """
    Detecta keywords típicos de remixes/edits en el texto
    (ya sea título completo o sufijo).
    """
    text = basic_normalize(text)
    found: List[str] = []
    for kw in _REMIX_KEYWORDS:
        if kw in text:
            found.append(kw)
    return found


# ============================================================
# Similitud básica (para scoring en matching)
# ============================================================

_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", flags=re.UNICODE)


def tokenize(text: str) -> List[str]:
    """
    Convierte un texto normalizado en lista de tokens alfanuméricos.
    """
    text = basic_normalize(text)
    if not text:
        return []
    tokens = [t for t in _TOKEN_SPLIT_RE.split(text) if t]
    return tokens


def token_set(text: str) -> Set[str]:
    return set(tokenize(text))


def jaccard_similarity(a: str, b: str) -> float:
    """
    Similitud de Jaccard entre dos textos (basada en tokens).
    Devuelve número entre 0.0 y 1.0.
    """
    set_a = token_set(a)
    set_b = token_set(b)
    if not set_a or not set_b:
        return 0.0
    inter = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(inter) / len(union) if union else 0.0


def title_similarity(a: str, b: str) -> float:
    """
    Similitud de título, teniendo en cuenta:
    - base normalizada
    - ligero bonus si comparten keywords de remix/version.

    Pensado para comparaciones MB ↔ Discogs.
    """
    base_a = normalize_title_for_search(a)
    base_b = normalize_title_for_search(b)

    base_sim = jaccard_similarity(base_a, base_b)

    # Bonus por remix/version keywords compartidas
    kw_a = set(detect_mix_keywords(a))
    kw_b = set(detect_mix_keywords(b))
    if kw_a and kw_b:
        if kw_a & kw_b:
            bonus = 0.2
        else:
            # uno dice 'remix' y el otro 'extended mix', etc.
            bonus = 0.1
    else:
        bonus = 0.0

    score = base_sim + bonus
    return max(0.0, min(1.0, score))


def artist_similarity(a: str, b: str) -> float:
    """
    Similitud de artista basada en nombres normalizados
    (sin feat./ft./featuring).
    """
    na = normalize_artist_name(a)
    nb = normalize_artist_name(b)
    return jaccard_similarity(na, nb)


# ============================================================
# Heurísticas auxiliares para compilaciones (Discogs)
# ============================================================

_COMPILATION_PATTERNS = [
    r"\bbest of\b",
    r"\bgreatest hits\b",
    r"\bthe best\b",
    r"\bcollection\b",
    r"\bcollections\b",
    r"\bultimate\b",
    r"\banthems\b",
    r"\bhits\b",
    r"\bdance anthems\b",
    r"\bvarious artists\b",
]


def is_probable_compilation(title: str) -> bool:
    """
    Marca títulos que probablemente sean compilaciones genéricas
    (Best Of, Greatest Hits, Collection, etc.).
    """
    norm = basic_normalize(title)
    for pat in _COMPILATION_PATTERNS:
        if re.search(pat, norm, flags=re.IGNORECASE):
            return True
    return False


# ============================================================
# Bloque de prueba rápida
# ============================================================

if __name__ == "__main__":
    # Pruebas muy simples en local
    examples = [
        "Lady (Hear Me Tonight)",
        "Lady [Extended Mix]",
        "Praise You (Purple Disco Machine Extended Remix)",
        "S.O.S (Skylark Mix)",
    ]

    for t in examples:
        base, suffix = extract_title_base_and_suffix(t)
        print("ORIG:", t)
        print("  base  :", base)
        print("  suffix:", suffix)
        print("  kw    :", detect_mix_keywords(t))
        print()

    print("Similitud títulos:")
    print(
        "Lady vs Lady (Hear Me Tonight):",
        title_similarity("Lady", "Lady (Hear Me Tonight)"),
    )
    print(
        "Praise You vs Praise You (Purple Disco Machine Extended Remix):",
        title_similarity(
            "Praise You", "Praise You (Purple Disco Machine Extended Remix)"
        ),
    )

    print("\nArtistas:")
    print(
        "normalize_artist_name('Artist feat. Singer'):",
        normalize_artist_name("Artist feat. Singer"),
    )
    print(
        "artist_similarity('Michael Jackson', 'Michael Jackson feat. Akon'):",
        artist_similarity("Michael Jackson", "Michael Jackson feat. Akon"),
    )
