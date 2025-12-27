from __future__ import annotations

import os
import shutil
import logging
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

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

    def __init__(self, use_discogs: bool = True, dry_run: bool = False):
        self.use_discogs = use_discogs
        self.dry_run = dry_run
        
        # Componentes
        self.pipeline = PipelineCore(use_discogs=use_discogs)
        self.tagger = Tagger(dry_run=dry_run)
        
        # Estadísticas
        self.stats = {
            "processed": 0,
            "matched": 0,
            "failed": 0,
            "skipped": 0
        }

    def process_library(self, input_dir: str, output_dir: str) -> None:
        """
        Procesa toda la biblioteca desde input_dir hacia output_dir.
        """
        input_dir = os.path.abspath(input_dir)
        output_dir = os.path.abspath(output_dir)

        if not os.path.exists(input_dir):
            logger.error(f"El directorio de entrada no existe: {input_dir}")
            return

        logger.info(f"Iniciando procesamiento de biblioteca...")
        logger.info(f"  Origen: {input_dir}")
        logger.info(f"  Destino: {output_dir}")

        # Obtener lista de archivos MP3
        files_to_process = self._scan_directory(input_dir)
        total_files = len(files_to_process)
        
        if total_files == 0:
            logger.warning("No se encontraron archivos MP3 en el directorio de origen.")
            return

        logger.info(f"Se encontraron {total_files} archivos para procesar.")

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
                futures[fut] = rel_path
            
            # Procesar resultados conforme llegan
            from concurrent.futures import as_completed
            # Procesar resultados conforme llegan
            from concurrent.futures import as_completed
            for future in as_completed(futures):
                try:
                    run_ok, is_match = future.result()
                    if run_ok:
                         self.stats["processed"] += 1
                         if is_match:
                             self.stats["matched"] += 1
                    else:
                         self.stats["failed"] += 1
                except Exception as e:
                    logger.error(f"Error en worker: {e}")
                    self.stats["failed"] += 1

        self._print_summary()

    def _process_single_file_safe(self, src, dest, idx, total) -> tuple[bool, bool]:
        """Wrapper thread-safe. Return (run_success, is_matched)."""
        try:
            is_match = self._process_single_file(src, dest)
            return True, is_match
        except Exception as e:
            logger.error(f"[{idx}/{total}] Fallo en {os.path.basename(src)}: {e}")
            return False, False

    def _scan_directory(self, path: str) -> List[str]:
        """Busca archivos MP3 recursivamente."""
        mp3_files = []
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                if filename.lower().endswith('.mp3'):
                    mp3_files.append(os.path.join(root, filename))
        return sorted(mp3_files)

    def _process_single_file(self, src_path: str, dest_path: str) -> None:
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
            return False

        src_lbl = "Discogs" if result.discogs_result and result.discogs_result.discogs_title else "MusicBrainz"
        if result.spotify_used: src_lbl = "Spotify"
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
        
        return True

    def _print_summary(self) -> None:
        logger.info("=== Resumen de Procesamiento ===")
        logger.info(f"Total Procesados: {self.stats['processed']}")
        logger.info(f"Exitosos (Match): {self.stats['matched']}")
        logger.info(f"Fallidos (Error): {self.stats['failed']}")
        logger.info("================================")

