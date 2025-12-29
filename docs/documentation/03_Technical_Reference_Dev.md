# Mp3 Metadata - Descripción Técnica del Proyecto
**Documento dirigido a:** Lead Developer / Equipo de Ingeniería
**Fecha:** 29 de Diciembre, 2025
**Stack:** Python 3.10+, Flet, Mutagen, AcoustID

---

## 1. Estructura Técnica del Proyecto (Arquitectura de Directorios)

El proyecto sigue una arquitectura **Modular Monolítica** con clara separación entre Lógica de Negocio (Backend) y Capa de Presentación (Frontend).

```
Mp3-Metadata/
├── backend/
│   └── mp3_autotagger/
│       ├── core/               # El Cerebro del sistema
│       │   ├── manager.py      # Orquestador Principal (Threads, Estados)
│       │   ├── pipeline.py     # Lógica de identificación (Audio -> Meta)
│       │   ├── tagger.py       # Escritura física en disco (Mutagen)
│       │   └── scanner.py      # Exploración de sistema de archivos
│       ├── modules/            # Clientes de APIs Externas
│       │   ├── acoustid.py     # Huella Digital
│       │   ├── musicbrainz.py  # Consulta MB
│       │   ├── discogs.py      # Consulta Discogs
│       │   └── spotify.py      # Consulta Spotify
│       └── data_structures/    # Modelos de Datos (Dataclasses)
│           └── schemas.py      # UnifiedTrackData, EditorialMetadata
├── frontend/
│   ├── main.py                 # Punto de entrada (Flet App)
│   └── views/
│       ├── dashboard.py        # Vista Principal (Tabla, Controles)
│       └── file_explorer.py    # Navegador de archivos custom
└── docs/                       # Documentación
```

## 2. Descripción Detallada de Componentes

### A. Core: `manager.py` (The State Manager)
Es la clase singleton `AppManager`.
*   **Responsabilidad:** Manejar el estado global, la cola de procesamiento y la comunicación UI-Backend.
*   **Concurrencia:** Utiliza `ThreadPoolExecutor` para paralelizar el escaneo y procesamiento de archivos. Esto evita congelar la UI de Flet.
*   **Lógica de Negocio:** Aquí reside la decisión de "Renombrar vs No Renombrar" basada en el umbral de confianza (`>= 0.95`).

### B. Core: `pipeline.py` (The Intelligence)
Es el corazón algorítmico.
*   **Flujo:** `Fingerprint -> AcoustID -> MBID -> Metadata Fetch -> Merge`.
*   **Algoritmo de Fusión:** Implementa lógica heurística para decidir qué dato priorizar (ej. Discogs tiene prioridad sobre MusicBrainz para "Estilos" de electrónica).

### C. Data Structures: `schemas.py`
Define `UnifiedTrackData`.
*   **Propósito:** Es un DTO (Data Transfer Object) agnóstico que desacopla las respuestas de las APIs de la lógica interna.
*   **Validación:** Implementa `__post_init__` para sanitización básica de tipos.

### D. Frontend: `dashboard.py`
Implementación de UI Reactiva con Flet.
*   **Componentes:** `DataTable` para resultados masivos.
*   **Optimización:** Renderiza celdas condicionalmente. Usa `e.control` para manejo de eventos eficientes (como los checkboxes).

---

## 3. Requerimientos Técnicos

### Sistema Operativo
*   **Desarrollo:** macOS (Optimizado para Apple Silicon M-Series).
*   **Producción:** Cross-platform (Windows/Linux soportados por librerías, pero validados en macOS).

### Dependencias Críticas (`requirements.txt`)
*   `flet`: UI Framework.
*   `mutagen`: Manipulación de ID3 tags.
*   `pyacoustid`: Wrapper para Chromaprint.
*   `requests`: Cliente HTTP robusto con manejo de Retries.
*   `python-dotenv`: Gestión de secretos.

### Credenciales Externas (Environment)
El sistema requiere claves API válidas para:
*   AcoustID (Client Key)
*   Spotify (Client ID + Secret)
*   Discogs (Personal Access Token)

---

## 4. Estándares de Código
*   **Typing:** Uso estricto de `Type Hints` (List, Dict, Optional, custom Dataclasses).
*   **Logging:** Sistema de logs centralizado en `utils/log.py` con niveles (DEBUG, INFO, WARNING, ERROR).
*   **Error Handling:** Bloques `try/except` granulares en cada módulo externo para evitar que el fallo de una API (ej. Spotify caída) detenga todo el proceso.

## 5. Deuda Técnica Actual y Riesgos
*   **Rate Limiting:** Las APIs de MusicBrainz y Discogs son estrictas. El `ThreadPoolExecutor` debe mantenerse calibrado (max 4 workers) para evitar Ban de IP.
*   **FFmpeg/Chromaprint:** Requiere binarios instalados en el sistema anfitrión (`brew install chromaprint`). Esto debe documentarse para el despliegue.
