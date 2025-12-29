# Mp3 Metadata - Music Library Standardizer

![Status](https://img.shields.io/badge/Status-Production-green) ![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/License-MIT-purple)

**Mp3 Metadata** es una solución de ingeniería de software diseñada para la **normalización, enriquecimiento y estandarización automática** de bibliotecas musicales digitales.

A diferencia de los etiquetadores convencionales, este sistema prioriza el **Audio Fingerprinting** sobre el nombre del archivo, garantizando una identificación precisa incluso en archivos mal nombrados.

---

## 🚀 Características Principales

*   **🎧 Identificación Acústica**: Usa **Chromaprint/AcoustID** para escuchar el audio y detectar la canción real.
*   **🌍 Triangulación de Datos**: Fusiona metadatos de **MusicBrainz** (Estructura), **Discogs** (Sello/Catálogo) y **Spotify** (Popularidad).
*   **🛡️ Semáforo de Confianza**: Solo renombra archivos si la certeza es **>= 95%**.
*   **🎹 DJ-Centric**: Detecta y respeta "Original Mix", "Extended Mix", "Dub Mix".
*   **🌑 UI Profesional**: Interfaz oscura de alto contraste (estilo Rekordbox/Serato) construida con **Flet**.

## 🛠️ Stack Tecnológico

*   **Frontend**: [Flet](https://flet.dev/) (Flutter wrapper para Python).
*   **Backend**: Python 3.10+ (Concurrente con ThreadPoolExecutor).
*   **Tagging**: `mutagen` (ID3v2.3/v2.4).
*   **Audio Analysis**: `pyacoustid` + `fpcalc`.

## 📦 Instalación

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/tu-usuario/mp3-metadata.git
    cd mp3-metadata
    ```

2.  **Crear entorno virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Mac/Linux
    # venv\Scripts\activate   # Windows
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Dependencias del Sistema (Chromaprint):**
    *   **macOS (Homebrew):** `brew install chromaprint`
    *   **Ubuntu/Debian:** `apt-get install libchromaprint-tools`
    *   **Windows:** Descargar `fpcalc.exe` y añadir al PATH.

5.  **Configurar Variables de Entorno:**
    Renombrar `.env.example` a `.env` y añadir tus claves API:
    ```env
    ACOUSTID_API_KEY=tu_clave
    SPOTIFY_CLIENT_ID=tu_id
    SPOTIFY_CLIENT_SECRET=tu_secreto
    DISCOGS_USER_TOKEN=tu_token
    ```

## 🎮 Uso

Ejecutar la aplicación:
```bash
python frontend/main.py
```

1.  Click en el icono de **Carpeta** para seleccionar directorio.
2.  Click en **SCAN** para analizar.
3.  Revisar resultados (Verde = Ready, Amarillo = Review).
4.  Click en **COMMIT** para aplicar cambios.

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

---
**Desarrollado con ❤️ para la comunidad de DJs y Archiveros.**
