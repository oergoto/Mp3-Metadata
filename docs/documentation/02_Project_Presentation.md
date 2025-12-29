# Mp3 Metadata - Presentación Oficial del Proyecto
**Documento dirigido a:** Junta Directiva / Stakeholders
**Fecha:** 29 de Diciembre, 2025
**Versión:** 1.0

---

## 1. Resumen Ejecutivo

**Mp3 Metadata** es una solución de ingeniería de software diseñada para la **normalización, enriquecimiento y estandarización automática** de bibliotecas musicales digitales. Utilizando algoritmos de huella acústica y triangulación de bases de datos globales, el sistema transforma colecciones de archivos desorganizados en activos digitales profesionales listos para su uso en radiodifusión, performance en vivo (DJing) y archivística.

### Descripción Corta
Sistema automatizado de gestión de metadatos musicales que utiliza Inteligencia Artificial y huella acústica para identificar, etiquetar y organizar archivos MP3 con precisión de nivel editorial.

### Descripción Larga
El ecosistema de la música digital sufre de una fragmentación masiva de datos: nombres de archivos incorrectos, metadatos ausentes y falta de estándares. **Mp3 Metadata** resuelve este problema eliminando la dependencia del "nombre del archivo" y centrando su análisis en el "audio real". Mediante el uso de tecnologías de **Fingerprinting Acústico (Chromaprint)**, el sistema identifica unívocamente cada grabación, consulta múltiples autoridades editoriales (MusicBrainz, Discogs, Spotify) y aplica un **protocolo de limpieza estricto**. El resultado es una biblioteca unificada, donde cada archivo posee trazabilidad completa de su origen, sello discográfico, año y arte de tapa, presentada bajo una interfaz gráfica de alto contraste optimizada para entornos profesionales.

---

## 2. Objetivos del Proyecto

### Objetivo Principal
Construir el estándar definitivo de gestión de bibliotecas musicales locales ("Local-First"), garantizando que cada archivo de audio posea una **Identidad Digital Única y Verificada**, eliminando el caos manual de la gestión de archivos.

### Objetivos Específicos
1.  **Automatización Total:** Reducir en un 99% el tiempo humano dedicado al etiquetado manual de música.
2.  **Integridad Editorial:** Asegurar que los metadatos (Sello, Catálogo, Año) provengan de fuentes verificadas y no de la opinión subjetiva del usuario.
3.  **Experiencia Profesional (UX):** Proveer una interfaz gráfica oscura, densa en información y de alto rendimiento, similar al estándar industrial (Rekordbox/Serato).
4.  **Preservación Digital:** Estandarizar el nombrado de archivos (`Título - Artista.mp3`) solo cuando la confianza de los datos supere el **95%**, protegiendo la integridad de la colección ante falsos positivos.

---

## 3. Historia y Contexto
El proyecto nace de la necesidad crítica en el flujo de trabajo de DJs profesionales y archivistas musicales. Las herramientas existentes (MusicBrainz Picard, Mp3Tag) son poderosas pero requieren una intervención manual excesiva o carecen de contexto específico para música electrónica (Remixes, Dubs, Ediciones Especiales).
**Mp3 Metadata** evoluciona desde scripts básicos de Python hacia una aplicación de escritorio completa (Estilo Rekordbox 7), integrando inteligencia de negocio específica: saber diferenciar un "Original Mix" de un "Radio Edit" es la clave de nuestro valor.

---

## 4. Funcionalidades Clave

*   **Identificación por Señal de Audio:** No importa si el archivo se llama `track_01.mp3`. El sistema escucha el audio para saber qué es.
*   **Triangulación de Datos (Data Fusion):**
    *   **MusicBrainz:** Estructura e IDs estables.
    *   **Discogs:** Datos precisos de vinilos y música electrónica underground.
    *   **Spotify:** Popularidad y metadatos de consumo masivo.
*   **Motor de Renombrado Seguro:** El sistema posee un "Semáforo de Confianza". Solo altera el sistema de archivos si la certeza es absoluta.
*   **Limpieza de Ruido:** Eliminación automática de textos basura como `[www.web.com]`, `(Official Video 4K)`, etc.

---

## 5. Sistemas

1.  **Core de Procesamiento (Backend):** Motor Python multihilo capaz de procesar cientos de archivos simultáneamente sin bloquear la interfaz.
2.  **Interfaz de Usuario (Frontend):** Construida con Flet (Flutter para Python), ofreciendo una experiencia nativa, fluida y visualmente impactante.
3.  **Data Pipeline:** Arquitectura de tubería que normaliza datos de fuentes dispares en un esquema común (`UnifiedTrackData`).
