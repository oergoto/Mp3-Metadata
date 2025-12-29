# Mp3 Metadata Project - Documentación Maestra (Holística)
**Versión del Documento:** 1.0
**Fecha:** 29 de Diciembre, 2025
**Rol:** Music Architecture & Engineering

---

## 1. Visión y Propósito del Proyecto (La Estrella del Norte)

**"Mp3 Metadata"** no es simplemente un "tagger" de MP3. Es un **Sistema de Normalización y Estandarización de Bibliotecas Musicales** diseñado específicamente para el contexto profesional de DJs, Productores y Archiveros Musicales.

Su misión es transformar una colección de archivos "sucios" (nombres incorrectos, sin etiquetas, descargados de YouTube, metadatos basura) en una **Biblioteca de Clase Mundial**, comparable a las bases de datos de Beatport o Apple Music.

### Filosofía "Dj-Centric"
A diferencia de herramientas genéricas (como MusicBrainz Picard estándar), este sistema:
1.  **Prioriza la Edición Original:** Distingue entre "Extended Mix", "Radio Edit" y "Dub Mix".
2.  **Valora el Sello Discográfico:** El número de catálogo (CAT#) es ciudadano de primera clase.
3.  **Estética Profesional:** La interfaz gráfica emula la experiencia "Dark Mode / High Contrast" de **Rekordbox 7**, diseñada para ser usada en entornos de poca luz.

---

## 2. Funcionalidades Core (¿Qué hace el sistema?)

### A. Identificación Acústica e Inteligente
No confiamos en los nombres de archivo. El sistema "escucha" el audio.
1.  **Huella Digital (Chromaprint):** Genera un hash único del audio real.
2.  **Triangulación de Bases de Datos:** Envía esa huella a **AcoustID** para obtener el ID único de la grabación (Recording ID).

### B. Enriquecimiento de Metadatos (Data Enrichment)
Una vez identificado el audio, el sistema consulta múltiples fuentes para construir el "Super-Metadato":
*   **Discogs:** Obtiene Sello, Catálogo, Año exacto, Arte de Tapa de alta resolución y Géneros específicos (ej. "Tech House" en lugar de "Electronic").
*   **Spotify:** Aporta datos de popularidad, fechas de lanzamiento digital y normalización de nombres de artistas.
*   **MusicBrainz:** Actúa como la columna vertebral de IDs estables.

### C. Normalización y Limpieza
*   **Sanitización de Texto:** Elimina basura como `(Official Video)`, `[320kbps]`, `www.sitioilegal.com`.
*   **Estandarización de Roles:** Separa "Artist" de "Feat. Artist" y "Remixer".

### D. Renombrado Estricto ("The God Tier Goal")
Solo si el sistema tiene una certeza absoluta (**Confianza >= 95%**), reescribe el nombre del archivo en el disco duro siguiendo el estándar sagrado:
> `Título - Artista.mp3`

### E. Feedback en Tiempo Real
*   **Dashboard Visual:** Tabla de datos interactiva con semáforo de confianza.
*   **Logs Detallados:** Auditoría paso a paso de qué decisión tomó la IA y por qué.

---

## 3. Arquitectura de Información (El Flujo de la Verdad)

El sistema sigue un modelo de **"Cascada de Prioridad"**. No todas las fuentes valen lo mismo.

### Jerarquía de Fuentes
1.  **MusicBrainz (MB):** **LA AUTORIDAD.** Provee los IDs estructurales. Si MB dice que es un ID, ese es el ID.
2.  **Discogs:** **EL EXPERTO EDITORIAL.** Si MB tiene el track, buscamos su equivalente en Discogs para llenar: *Sello Discográfico, Número de Catálogo, Estilos Electrónicos precisos*.
3.  **Spotify:** **EL POPULAR.** Se usa para desempatar, obtener portadas digitales limpias e ISRC si faltan.

### Flujo de Datos (Pipeline)
1.  **INPUT:** Archivo MP3 Crudo (`track01.mp3`).
2.  **HASHING:** Generación de Fingerprint.
3.  **QUERY:** Consulta a AcoustID -> Obtiene MBID.
4.  **METADATA FETCH:**
    *   Con MBID -> Consulta MusicBrainz API.
    *   Con datos de MB -> Busca match en Discogs API.
    *   Fallback -> Busca por texto en Spotify API.
5.  **MERGE & SCORE:** Unifica datos y calcula el **Score de Confianza (0-100%)**.
6.  **DECISIÓN:**
    *   **< 95%:** Se muestra en amarillo/rojo. Requiere revisión humana. **NO SE RENOMBRA**.
    *   **>= 95%:** Se marca "READY". Se permite renombrado automático.
7.  **OUTPUT:** Escritura de Tags ID3v2.3 (Estándar de la industria para compatibilidad con CDJs Pioneer).

---

## 4. Experiencia de Usuario (User Flows)

### Flujo Principal: "El Ciclo de Limpieza"
1.  **Scan:** El usuario elige una carpeta. El sistema escanea recursivamente.
2.  **Análisis (Wait):** El usuario ve la Barra de Progreso y los Logs en tiempo real.
3.  **Revisión (The Dashboard):**
    *   El usuario ve una Tabla estilo Excel.
    *   Las filas **Verdes** (>95%) ya están marcadas para procesar.
    *   Las filas **Amarillas** requieren su ojo experto. Puede marcarlas manualmente si está de acuerdo.
4.  **Commit (La Acción):** El usuario pulsa "COMMIT".
    *   El sistema escribe los tags en los archivos seleccionados.
    *   El sistema renombra los archivos de alta confianza.
    *   Genera un reporte final.

---

## 5. Hoja de Ruta y Expansión (El Futuro)

Este proyecto tiene una arquitectura modular que permite escalar hacia:

### A. Edición Manual Avanzada (Editor 1 a 1)
*   **Feature:** Hacer doble clic en una fila para abrir un editor modal.
*   **Uso:** Corregir manualmente un "Remix" que la IA detectó como "Original Mix". Buscar manualmente en Discogs poniendo el ID.

### B. Visualización de Audio
*   **Feature:** Integrar librerías de análisis de onda para mostrar el "Waveform" en el dashboard.
*   **Uso:** Detectar visualmente archivos corruptos o silencios.

### C. Gestión de Playlists (m3u8)
*   **Feature:** Exportar las selecciones directamente a listas de reproducción compatibles con Rekordbox/Traktor.

### D. Modo "Server / Headless"
*   **Feature:** Ejecutar el backend en un NAS (Synology/Raspberry Pi) que vigile una carpeta "INCOMING" y procese automáticamente todo lo que caiga ahí 24/7.

### E. Integración con Hardware DJ
*   **Feature:** Exportación directa a USB preparado para CDJ (con base de datos Pioneer/Rekordbox XML), saltando el paso del software de escritorio.

---
**Este documento representa el conocimiento total del estado actual del proyecto Mp3 Metadata.**
