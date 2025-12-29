# Mp3 Metadata - Manual Técnico de UX/UI
**Documento dirigido a:** Lider UX/UI & Frontend Developer
**Fecha:** 29 de Diciembre, 2025
**Estética:** Inspirada en Rekordbox 7 / Serato (Dark, High Contrast)

---

## 1. Arquitectura de Información

### A. Sitemap de la Aplicación
Actualmente es una aplicación "Single View Application" (SPA) con diálogos modales, para maximizar la eficiencia del operador.

```
[Main Window]
  ├── [Status Deck (Top)]
  │     ├── Path Selector (Breadcrumbs)
  │     └── KPI Widgets (Procesados, Éxitos, Fallos)
  ├── [Action Toolbar]
  │     ├── Scan Button
  │     ├── Commit Button
  │     └── Progress Bar (Neon Green)
  └── [Results Area (Center - Scrollable)]
        └── DataTable (Filas Interactivas)

[Modals]
  ├── [File Explorer Dialog] (Navegación de árbol de carpetas)
  └── [Settings Dialog] (Futuro)
```

### B. Tags de Información (Columnas de Datos)
La tabla principal expone la siguiente taxonomía de información para el usuario:
1.  **Status:** Semáforo visual (Estado del proceso).
2.  **Cover Art:** Miniatura visual (30x30px).
3.  **Filename:** Nombre actual del archivo.
4.  **Original Title/Artist:** Comparativa visual.
5.  **New Title/Artist:** Propuesta de cambio.
6.  **Confidence:** Porcentaje crítico (%).
7.  **Source:** Icono de fuente (MB, Discogs, Spotify).
8.  **Editorial:** Catálogo, Año, Género (Datos secundarios en gris).

### C. User Journey Map (Flujos Críticos)

#### Escenario 1: El Flujo Perfecto (Happy Path)
1.  **Inicio:** Usuario abre app. Ve dashboard vacío y limpio.
2.  **Selección:** Clic en ícono de carpeta -> Abre Modal -> Navega -> Selecciona Carpeta.
3.  **Escaneo:** Clic en "SCAN".
    *   *Feedback:* Barra de progreso avanza. Logs aparecen abajo.
4.  **Revisión:** Tabla se llena.
    *   Filas con 95%+ aparecen **Verdes** y con **Checkbox Pre-marcado**.
    *   Datos editoriales llenos.
5.  **Acción:** Clic en "COMMIT".
    *   *Feedback:* Botón cambia texto a "Processing...".
    *   *Resultado:* Archivos se renombran. Tabla se actualiza.

#### Escenario 2: La Desconfianza (Low Confidence)
1.  **Revisión:** Usuario nota una fila **Amarilla** (Confidence 70%).
    *   Sistema: No marcó el checkbox automáticamente.
2.  **Interacción:** Usuario lee los metadatos propuestos.
    *   *Decisión:* "Es correcto, es un remix raro".
3.  **Override:** Usuario hace clic manual en el Checkbox.
    *   *Sistema:* Fuerza el estado visual a "Selected".
4.  **Commit:** El archivo se procesa bajo responsabilidad del usuario.

#### Escenario 3: El Error (No Match)
1.  **Revisión:** Fila **Roja** (Confidence 0% o <50%).
    *   Status: "REJECTED".
2.  **Acción:** Usuario ignora la fila (Checkbox deshabilitado o desmarcado).
3.  **Commit:** El archivo se ignora. Se mantiene intacto en disco.

---

## 2. Taxonomía de Estados (Semáforo de Confianza)

Definición rigurosa de cómo el backend comunica estados al frontend visual.

| Estado Backend | Confianza (%) | Color UI | Texto UI | Comportamiento |
| :--- | :--- | :--- | :--- | :--- |
| **READY (High)** | >= 95% | **Verde (#00C853)** | READY | Auto-Select: ON <br> Rename: YES |
| **READY (Mid)** | 50% - 94% | **Ámbar (#FFAB00)** | REVIEW | Auto-Select: OFF <br> Rename: NO (Tag Only) |
| **REJECTED** | < 50% | **Rojo (#D50000)** | REJECTED | Auto-Select: OFF <br> Interact: Disabled |
| **PROCESSING** | N/A | Azul (#00A4FF) | ... | Spinner activo |

---

## 3. Stack Tecnológico Frontend
**Framework:** **Flet** (Python wrapper sobre Flutter).

*   **Rationale:** Permite desarrollo ultrarrápido en Python, pero entrega una UI renderizada en Flutter (Skia Engine), garantizando 60FPS y renderizado de fuentes sub-pixel perfecto.
*   **Design System:** Material Design 3 (adaptado a "Pro Audio Dark Theme").
*   **Componentes Clave:**
    *   `ft.DataTable`: Manejo virtualizado de listas largas.
    *   `ft.ProgressBar`: Feedback visual crítico.
    *   `ft.ControlEvent`: Manejo reactivo de estados.

## 4. Stack Tecnológico Backend
**Lenguaje:** Python 3.10+

*   **API Client:** `requests` (Sync) ejecutado dentro de `ThreadPoolExecutor` para simular asincronía sin bloquear el Main Thread de Flet.
*   **Audio Analysis:** `chromaprint` (librería C++ con bindings de Python `pyacoustid`). Es el componente más pesado y crítico.
*   **Tagging:** `mutagen`. Soporta ID3v2.3 (Estándar de compatibilidad) y ID3v2.4.
*   **Lógica:** Pura Python. Sin dependencias de frameworks web pesados (No Django/Flask). Arquitectura orientada a servicios (SOA) interna.
