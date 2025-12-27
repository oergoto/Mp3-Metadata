#!/usr/bin/env python3
import argparse
import os
import sys

# Asegurar que el directorio actual está en el path para las importaciones
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mp3_autotagger.core.manager import LibraryManager
from mp3_autotagger.utils.log import setup_logging

def main():
    parser = argparse.ArgumentParser(description="Mp3 Metadata MagicTagger - RAW to CLEAN Processor")
    parser.add_argument("input_path", help="Directorio RAW de origen (Solo lectura)")
    parser.add_argument("output_path", help="Directorio CLEAN de destino (Escritura)")
    parser.add_argument("--write", "-w", action="store_true", help="Ejecutar escritura real (Si no se usa, es DRY-RUN)")
    parser.add_argument("--no-discogs", action="store_true", help="Saltar búsqueda en Discogs")
    
    args = parser.parse_args()
    
    # Configurar Logging
    setup_logging("mp3_pipeline.log")
    import logging
    logger = logging.getLogger(__name__)
    
    # Validar paths
    if not os.path.exists(args.input_path):
        logger.error(f"La ruta de origen '{args.input_path}' no existe.")
        sys.exit(1)
        
    # Crear output si no existe (solo si vamos a escribir, o avisar)
    if not os.path.exists(args.output_path) and args.write:
        logger.info(f"Creando directorio destino: {args.output_path}")
        os.makedirs(args.output_path, exist_ok=True)

    # Configuración
    dry_run = not args.write
    use_discogs = not args.no_discogs
    
    logger.info("=== Mp3 Metadata Pipeline (Manager Mode) ===")
    logger.info(f"Modo DRY-RUN: {'SI' if dry_run else 'NO'}")
    logger.info(f"Input: {args.input_path}")
    logger.info(f"Output: {args.output_path}")

    try:
        manager = LibraryManager(use_discogs=use_discogs, dry_run=dry_run)
        manager.process_library(args.input_path, args.output_path)
    except Exception as e:
        logger.critical(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
