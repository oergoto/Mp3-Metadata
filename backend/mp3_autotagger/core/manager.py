from __future__ import annotations

import os
import shutil
import logging
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
from mutagen.id3 import ID3, APIC
from datetime import datetime

from .pipeline import PipelineCore
from .tagger import Tagger
from mp3_autotagger.core.models import TrackMetadataBase

logger = logging.getLogger(__name__)

class LibraryManager:
    """
    Gestor principal de la biblioteca.
    Se encarga de:
    1. Escanear directorio RAW (recursivo).
    2. Replicar estructura en directorio CLEAN.
    3. Copiar archivos de forma segura.
    4. Orquestar el etiquetado (Pipeline + Tagger).
    """

    def __init__(self, use_discogs: bool = True, dry_run: bool = False, progress_callback=None):
        self.use_discogs = use_discogs
        self.dry_run = dry_run # If true, we simulate changes and generate a report
        self.progress_callback = progress_callback
        
        # Componentes
        self.pipeline = PipelineCore(use_discogs=use_discogs)
        self.tagger = Tagger(dry_run=dry_run)
        self.library_path = "" # Added
        self.scan_results = [] # Modified from last_scan_results
        self.last_results_map = {} # Map index -> Result object # Added
        
        # Cache Config # Added
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) # Added
        self.cover_cache_dir = os.path.join(self.base_dir, "cache", "covers") # Added
        os.makedirs(self.cover_cache_dir, exist_ok=True) # Added
        
        # Estadísticas
        self.stats = {
            "processed": 0,
            "success": 0, # Modified from matched
            "rescued": 0, # Added
            "failed": 0
        }

        # Custom Rename Format (Phase 4)
        self.rename_pattern = "{artist} - {title}"

        self.last_scan_results = [] # Store results for UI interaction

    def _get_cover_art(self, file_path: str) -> str:
        """
        Extracts embedded cover art (APIC) from MP3.
        Returns absolute path to cached image, or empty string if none.
        Uses md5 of file path as cache key.
        """
        try:
            # Cache Key
            file_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
            cache_path = os.path.join(self.cover_cache_dir, f"{file_hash}.jpg")
            
            # Return cached if exists
            if os.path.exists(cache_path):
                return cache_path
            
            # Extract
            audio = ID3(file_path)
            for tag in audio.values():
                if isinstance(tag, APIC):
                    # Found art
                    with open(cache_path, 'wb') as img:
                        img.write(tag.data)
                    return cache_path
                    
        except Exception as e:
            # logger.warning(f"Error extracting art for {os.path.basename(file_path)}: {e}")
            pass
            
        return ""

    def _notify(self, msg: str):
        if self.progress_callback:
            # Stats are passed empty or current
            self.progress_callback(msg, 0, 0, self.stats)

    def process_library(self, input_dir: str, output_dir: str) -> None:
        """
        Procesa toda la biblioteca desde input_dir hacia output_dir.
        """
        self.last_scan_results = [] # Reset results
        input_dir = os.path.abspath(input_dir)
        output_dir = os.path.abspath(output_dir)

        self._notify(f"Verificando directorio: {input_dir}")

        if not os.path.exists(input_dir):
            logger.error(f"El directorio de entrada no existe: {input_dir}")
            self._notify(f"ERROR: No existe directorio {input_dir}")
            return

        logger.info(f"Iniciando procesamiento de biblioteca...")
        self._notify("Escanando archivos MP3...")

        # Obtener lista de archivos MP3
        files_to_process = self._scan_directory(input_dir)
        total_files = len(files_to_process)
        
        if total_files == 0:
            logger.warning("No se encontraron archivos MP3 en el directorio de origen.")
            self._notify("No se encontraron archivos MP3.")
            return

        logger.info(f"Se encontraron {total_files} archivos para procesar.")
        self._notify(f"Encontrados {total_files} archivos. Iniciando workers...")

        # Procesamiento Paralelo
        # Usamos max_workers=4 para equilibrar velocidad vs rate limits
        workers = 4
        logger.info(f"Iniciando procesamiento paralelo con {workers} workers...")
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Diccionario para mantener orden de logs si fuera necesario, 
            # pero aquí priorizamos la ejecución.
            # Mapeamos future -> (index, rel_path, src, dest)
            futures = {}
            for i, src_path in enumerate(files_to_process, 1):
                rel_path = os.path.relpath(src_path, input_dir)
                dest_path = os.path.join(output_dir, rel_path)
                
                # Enviamos tarea
                fut = executor.submit(self._process_single_file_safe, src_path, dest_path, i, total_files)
                futures[fut] = (i, rel_path) # Store index (1-based) to order logically if needed
            
            # Procesar resultados conforme llegan
            from concurrent.futures import as_completed
            
            # Pre-fill list with None to allow index-based insertion? 
            # Or just append. Appending is easier but order is random.
            # UI expects specific order? Table rows match log order usually.
            # Let's assume UI handles mapping via an ID or Index we provide.
            
            for future in as_completed(futures):
                try:
                    res_tuple = future.result()
                    # Unpack: (run_ok, is_match, result_object)
                    # We need to change _process_single_file_safe signature to return result object too
                    run_ok, is_match, res_obj = res_tuple
                    
                    if run_ok:
                         self.last_scan_results.append(res_obj) # Add to storage
                         self.stats["processed"] += 1
                         if is_match:
                             self.stats["success"] += 1
                    else:
                         self.stats["failed"] += 1
                except Exception as e:
                    logger.error(f"Error en worker: {e}")
                    self.stats["failed"] += 1

        self._print_summary()
        
    def apply_batch(self, indices: List[int]) -> int:
        """
        [Phase 4 + 6] 
        - APPROVED (indices): Writes tags and RENAMES to 'Title - Artist.mp3'.
        - REJECTED (others): Moves to '[Folder] - RAW'.
        """
        if not self.last_scan_results:
            logger.warning("No hay resultados de escaneo previos para aplicar.")
            return 0
            
        logger.info(f"Procesando lote: {len(indices)} aprobados vs {len(self.last_scan_results) - len(indices)} rechazados.")
        
        success_count = 0
        real_tagger = Tagger(dry_run=False)
        
        # Prepare RAW directory (Isolation)
        raw_dir = None
        try:
             # Infer base directory from first file
             first_file = self.last_scan_results[0].track_metadata.filepath_original
             base_dir = os.path.dirname(first_file)
             folder_name = os.path.basename(base_dir)
             raw_dir = os.path.join(base_dir, f"{folder_name} - RAW")
        except Exception:
             pass

        for idx, result in enumerate(self.last_scan_results):
            if not result: continue
            
            meta = result.track_metadata
            current_path = meta.filepath_original
            
            # --- APPROVED TRACKS ---
            if idx in indices:
                try:
                    # 1. Write Tags
                    ok = real_tagger.write_metadata(meta)
                    if ok:
                        # 2. Rename (Title - Artist.mp3)
                        self._rename_optimized(meta)
                        success_count += 1
                except Exception as e:
                    logger.error(f"Error procesando {getattr(meta, 'title', 'Unknown')}: {e}")
            
            # --- REJECTED TRACKS (Isolation) ---
            else:
                 if raw_dir:
                     self._isolate_file(current_path, raw_dir)

        logger.info(f"Cambios aplicados. Exitosos: {success_count}. El resto se movió a RAW.")
        return success_count

    def _rename_optimized(self, meta):
        """Renames file to 'Title - Artist.mp3'."""
        try:
            # Sanitize
            import re
            def clean(s): return re.sub(r'[<>:"/\\|?*]', '', str(s)).strip()
            
            title = clean(meta.title)
            artist = clean(meta.artist_main)
            
            if not title or not artist: 
                logger.warning(f"Rename skipped: Missing title='{title}' or artist='{artist}'")
                return
            
            new_name = f"{title} - {artist}.mp3"
            dir_path = os.path.dirname(meta.filepath_original)
            new_path = os.path.join(dir_path, new_name)
            
            logger.info(f"Renaming '{meta.filepath_original}' -> '{new_path}'")
            
            if new_path != meta.filepath_original and not os.path.exists(new_path):
                os.rename(meta.filepath_original, new_path)
                meta.filepath_original = new_path 
            elif os.path.exists(new_path):
                logger.warning(f"Rename skipped: Target exists '{new_name}'")
        except Exception as e:
            logger.warning(f"Rename failed: {e}")

    def _isolate_file(self, src_path, raw_dir):
        """Moves file to RAW folder."""
        try:
            if not os.path.exists(raw_dir):
                os.makedirs(raw_dir, exist_ok=True)
                
            fname = os.path.basename(src_path)
            dest_path = os.path.join(raw_dir, fname)
            
            logger.info(f"Isolating Rejected: {fname}")
            
            # Avoid overwrite if possible, or overwrite if requested. 
            # Moving...
            if os.path.exists(src_path):
                shutil.move(src_path, dest_path)
        except Exception as e:
            logger.warning(f"Isolation failed for {src_path}: {e}")

    def _print_summary(self) -> None:
        logger.info("=== Resumen de Procesamiento ===")
        logger.info(f"Total Procesados: {self.stats['processed']}")
        logger.info(f"Exitosos (Match): {self.stats['matched']}")
        logger.info(f"Fallidos (Error): {self.stats['failed']}")
        logger.info("================================")

    def _process_single_file_safe(self, src, dest, idx, total) -> tuple[bool, bool, Optional[object]]:
        """Wrapper thread-safe. Return (run_success, is_matched, result_object)."""
        try:
            result_obj = self._process_single_file(src, dest)
            is_match = result_obj is not None
            
            # Notificar progreso si hay callback
            if self.progress_callback:
                 fname = os.path.basename(src)
                 status = "MATCH" if is_match else "NO MATCH"
                 msg = f"[{idx}/{total}] {status}: {fname}"
                 
                 # Extract details for UI
                 details = {}
                 if is_match:
                     # Confidence logic: Try track_meta first, then discogs
                     conf = getattr(result_obj.track_metadata, "match_confidence", 0.0)
                     if not conf and result_obj.discogs_result:
                         conf = result_obj.discogs_result.discogs_confidence_score
                     
                     # Store in list for UI access (Thread-safe append?)
                     # List append is atomic in CPython, should be fine for now.
                     # We rely on 'details' having an 'index' to map back if order meshes up,
                     # but scan_results order in main depends on callback. 
                     # Better: use the index passed to callback? No, idx comes from enumerate.
                     # We need to store standard result in self.last_scan_results
                     # BUT wait, this is running in thread. 
                     # self.last_scan_results is global in manager instance.
                     # We should resize list first or use a dict if random access needed.
                     # Let's use a dict self.last_results_map = {idx: result} then convert to list.
                     pass 

                     # Convert to percentage if it's 0-1
                     if conf <= 1.0: conf *= 100
                         
                     # Pre-calculate durations
                     local_dur = 0.0
                     local_dur_str = "--:--"
                     diff = 0.0
                     
                     try:
                        from mutagen import File
                        f = File(src)
                        if f and f.info and f.info.length:
                             local_dur = f.info.length
                             local_dur_str = f"{int(local_dur/60)}:{int(local_dur%60):02d}"
                             
                             # Calculate Diff
                             matched_dur_ms = result_obj.track_metadata.audio.duration_ms
                             if matched_dur_ms:
                                 matched_dur = matched_dur_ms / 1000.0
                                 diff = round(local_dur - matched_dur, 2)
                     except:
                         pass

                     # Extract Editorial & IDs
                     tm = result_obj.track_metadata
                     ed = tm.editorial
                     ids = tm.ids
                     
                     details = {
                         # Basic
                         "filename": os.path.basename(src), 
                         "original_filename": os.path.basename(src), 
                         "title": tm.title,
                         "artist": tm.artist_main,
                         "album": tm.album,
                         "year": tm.year,
                         
                         # DataLayer Expanded
                         "genre": tm.genre_main or "",
                         "styles": ", ".join(ed.styles) if ed.styles else "",
                         "publisher": ed.publisher or "",
                         "isrc": ids.isrc or "",
                         "cat_number": ed.catalog_number or "",
                         "country": ed.country or "",
                         "format": ed.media_format.value if hasattr(ed.media_format, 'value') else str(ed.media_format or ""),
                         "release_status": ed.release_status.value if hasattr(ed.release_status, 'value') else str(ed.release_status or ""),
                         "release_type": ed.release_type.value if hasattr(ed.release_type, 'value') else str(ed.release_type or ""),
                         # "copyright":  # Not in standard model yet? Check schema logic or use publisher as proxy
                         "credits": "", # Placeholder. Need rich credits string
                         
                         "cover_path": self._get_cover_art(src),
                         
                         # IDs & URLs
                         "mb_track_id": ids.musicbrainz_track_id or "",
                         "mb_release_id": ids.musicbrainz_release_id or "",
                         "acoustid": ids.acoustid_fingerprint[:15]+"..." if ids.acoustid_fingerprint else "",
                         "url_spotify": f"open.spotify.com/track/{ids.spotify_id}" if ids.spotify_id else "",
                         "url_discogs": f"discogs.com/release/{ids.discogs_release_id}" if ids.discogs_release_id else "",

                         # Logic
                         "confidence": conf,
                         "source": "Spotify" if result_obj.spotify_used else ("Discogs" if result_obj.discogs_result else "MusicBrainz"),
                         "duration_str": local_dur_str, 
                         "duration_diff": diff, 
                         "rescued": False 
                     }
                     
                     self.progress_callback(msg, idx, total, self.stats, details)

            return True, is_match, result_obj
        except Exception as e:
            logger.error(f"[{idx}/{total}] Fallo en {os.path.basename(src)}: {e}")
            return False, False, None

    def _scan_directory(self, path: str) -> List[str]:
        """Busca archivos MP3 recursivamente."""
        mp3_files = []
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                if filename.lower().endswith('.mp3'):
                    mp3_files.append(os.path.join(root, filename))
        return sorted(mp3_files)

    def _process_single_file(self, src_path: str, dest_path: str):
        """
        1. Copia archivo a destino (creando carpetas).
        2. Ejecuta pipeline sobre el destino.
        3. Escribe tags.
        """
        # 1. Preparar destino
        dest_dir = os.path.dirname(dest_path)
        if not os.path.exists(dest_dir):
            if not self.dry_run:
                os.makedirs(dest_dir, exist_ok=True)
            else:
                pass # logger.debug(f"[DryRun] Crearía directorio: {dest_dir}")

        # 2. Copiar archivo (si no existe o si se fuerza overwrite - por ahora overwritamos soft si cambió tamaño)
        # Para garantizar idempotencia simple, copiamos siempre si no es dry run
        if not self.dry_run:
            try:
                shutil.copy2(src_path, dest_path)
            except Exception as e:
                logger.error(f"Error copiando archivo: {e}")
                return
        
        target_file = dest_path if not self.dry_run else src_path
        
        # 3. Identificar (Pipeline)
        # Ojo: Si es dry-run, el pipeline analiza el SOURCE, pero Tagger simula escritura.
        # Si es real, pipeline analiza DEST y Tagger escribe en DEST.
        
        result = self.pipeline.process_file(target_file)
        
        tm = result.track_metadata
        # Check for meaningful match (MB ID, Discogs ID, or Spotify ID)
        has_match = (
            (tm.ids.musicbrainz_track_id is not None) or
            (tm.ids.discogs_release_id is not None) or
            (tm.ids.spotify_id is not None)
            # or (tm.title and tm.artist_main) # Conservative: Only count ID-backed matches as "Match"
        )
            
        if not has_match:
            logger.warning(f"  -> SIN COINCIDENCIA para: {os.path.basename(src_path)}")
            # Aún así ya se copió el archivo, así que queda el original en CLEAN (que es deseable, fallback manual)
            return None

        src_lbl = "Discogs" if result.discogs_result and result.discogs_result.discogs_title else "MusicBrainz"
        if result.spotify_used: src_lbl = "Spotify"
        if result.spotify_used: src_lbl = "Spotify"
        
        # GUARDRAIL: Confidence Check (Phase 28 Optimization)
        # If match confidence is too low (e.g. < 50%), treat as NO MATCH to avoid bad tagging.
        final_conf = tm.match_confidence
        if final_conf == 0.0 and result.discogs_result and result.discogs_result.discogs_confidence_score:
             final_conf = result.discogs_result.discogs_confidence_score

        if final_conf > 0 and final_conf < 0.5:
             logger.warning(f"  -> MATCH DESCARTADO (Confianza Baja {final_conf:.2f}): {os.path.basename(src_path)}")
             return None

        logger.info(f"  -> MATCH ({src_lbl}): {result.get_display_title()} / {result.get_display_artist()}")
        
        # 4. Escribir Tags
        # Actualizamos el path del metadata para apuntar al archivo destino REAL
        tm.filepath_original = dest_path 
        
        # En dry-run "dest_path" no existe, así que Tagger debe saber que no debe verificar existencia si es dry-run
        # El Tagger actual chequea `if not os.path.exists(path): return False`.
        # Si dry-run es True, Tagger debería simular.
        # PERO: Tagger.write_metadata chequea existencia antes de dry_run check.
        # SOLUCIÓN: Si es dry_run, pasamos el src_path al tagger para que "vea" el archivo, 
        # pero como Tagger.dry_run es True, no escribirá.
        
        if self.dry_run:
            tm.filepath_original = src_path

        success = self.tagger.write_metadata(tm)
        if not success:
            logger.warning("  -> Fallo en escritura de tags.")
        
        return result

    def _print_summary(self) -> None:
        logger.info("=== Resumen de Procesamiento ===")
        logger.info(f"Total Procesados: {self.stats['processed']}")
        logger.info(f"Exitosos (Match): {self.stats['success']}")
        logger.info(f"Fallidos (Error): {self.stats['failed']}")
        logger.info("================================")

    def export_csv(self, data: List[dict], output_dir: Optional[str] = None) -> str:
        """
        Exporta los resultados del escaneo a un archivo CSV.
        Retorna la ruta absoluta del archivo generado.
        """
        if not data:
            return ""

        # Ensure reports dir or use selected
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
            
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"scan_report_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # Get headers from first item (superset if needed, but UI struct is consistent)
        fieldnames = [
            "status", "filename", "original_filename", 
            "artist", "title", "album", "year", 
            "genre", "styles", "publisher", "cat_number",
            "country", "format", "release_type", "release_status",
            "isrc", "duration_str", "duration_diff", "confidence", "source", 
            "url_spotify", "url_discogs", "mb_track_id", "mb_release_id", "acoustid"
        ]
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                for row in data:
                    # Determine status for CSV based on confidence/rescued
                    status = "READY"
                    if row.get("confidence", 0) < 50: status = "REJECTED"
                    elif row.get("rescued"): status = "RESCUED"
                    
                    # Inject status if missing from row (UI computes it)
                    row_copy = row.copy()
                    row_copy["status"] = status
                    
                    writer.writerow(row_copy)
                    
            logger.info(f"Reporte CSV generado: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error generando CSV: {e}")
            raise e

