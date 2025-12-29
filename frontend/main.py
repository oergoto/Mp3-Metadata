import flet as ft
import sys
import os
import threading
import time

# --- Setup Paths to import Backend ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.append(os.path.join(PROJECT_ROOT, "backend"))

# Import Views
from views.dashboard import DashboardView

# Global Manager Reference
manager = None

def main(page: ft.Page):
    # --- Window Config ---
    page.title = "Mp3 Metadata Analysis (Rekordbox 7 Style)"
    
    # Init Logger
    from mp3_autotagger.utils.log import setup_logging
    setup_logging(verbose=True)
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#000000"  # True Black
    page.padding = 0 # Full bleed
    
    # Rekordbox 7 Theme
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary="#2979FF",        # Electric Blue
            secondary="#00B0FF",      # Lighter Cyan Blue
            surface="#111111",        # Dark Gray Surfaces
            background="#000000",
            error="#D32F2F",
            on_background="#FFFFFF",
            on_surface="#E0E0E0",
        ),
        font_family="Roboto", # Clean, modern sans-serif
        visual_density=ft.VisualDensity.COMPACT, # Dense UI
    )
    
    # Fonts (if we were loading custom fonts, we'd do it here)
    
    # --- Controller Logic ---
    
    def on_start_scan(path, dry_run, use_discogs):
        """Callback triggered by Dashboard Scan Button"""
        if not path or not os.path.exists(path):
            dashboard.add_log(f"Error: Ruta inválida {path}")
            page.update()
            return

        # Run in Thread
        t = threading.Thread(target=run_backend_logic, args=(path, dry_run, use_discogs))
        t.start()
        
    def on_commit(indices):
        """Callback triggered by Dashboard Commit Button"""
        if not manager:
            dashboard.add_log("Error: Manager no inicializado.")
            return
            
        dashboard.add_log(f"Iniciando escritura en {len(indices)} archivos...")
        page.update()
        
        def run_commit():
            updated = manager.apply_batch(indices)
            dashboard.add_log(f"=== PROCESO DE ESCRITURA FINALIZADO: {updated} archivos actualizados ===")
            page.update()
            
        t = threading.Thread(target=run_commit)
        t.start()

    def run_backend_logic(path, is_dry, use_discogs):
        global manager
        
        # --- UI Callback ---
        def on_progress(msg, idx, total, stats, details=None):
            try:
                # Update Log
                dashboard.add_log(msg) 
                
                # Update Stats
                dashboard.update_stats(
                    stats["processed"], 
                    stats["success"], 
                    stats.get("rescued", 0),
                    stats["failed"]
                )
                
                # Add Row to Grid
                if details:
                    # Inject index for callback
                    details["index"] = len(dashboard.data_table.rows) 
                    dashboard.add_row(details)
                
                page.update()
            except Exception as e:
                print(f"UI UPDATE ERROR: {e}")

        try:
             # Lazy Import
             from mp3_autotagger.core.manager import LibraryManager
             
             dashboard.add_log(f"=== INICIANDO ESCANEO (DryRun={is_dry}) ===")
             dashboard.add_log(f"Target: {path}")
             page.update()
             
             # Connect to Manager Logic
             manager = LibraryManager(use_discogs=use_discogs, dry_run=is_dry, progress_callback=on_progress)
             
             # Show loading state logic could go here if we had a specific spinner
             
             output_path = path 
             if is_dry:
                 output_path = path 
             
             manager.process_library(path, output_path)
             
             dashboard.add_log("--- ESCANEO FINALIZADO ---")
             dashboard.enable_commit()
             page.update()

        except Exception as e:
            dashboard.add_log(f"ERROR CRÍTICO: {e}")
            import traceback
            traceback.print_exc()

    def on_export_csv(data, target_path=None):
        try:
            from mp3_autotagger.core.manager import LibraryManager
            mgr = LibraryManager() # Helper instance
            filepath = mgr.export_csv(data, target_path)
            
            page.snack_bar = ft.SnackBar(content=ft.Text(f"CSV generado: {filepath}"))
            page.snack_bar.open = True
            page.update()
        except Exception as e:
             dashboard.add_log(f"Error Exporting CSV: {e}")
             page.update()

    # --- View Initialization ---
    try:
        dashboard = DashboardView(page, on_start_scan, on_commit, on_export_csv)
    except Exception as e:
        page.add(ft.Text(f"Error cargando UI: {e}", color="red"))
        import traceback
        traceback.print_exc()
        return
    
    # --- Drag & Drop ---
    def on_drag_accept(e: ft.DragTargetAcceptEvent):
        src = page.get_control(e.src_id)
        # Web/Native drag data handling varies, but normally e.data (or control data)
        # For OS file drag: e.data should contain path if supported, or check e.page...
        # Flet desktop drag-drop works via GetControl if internal.
        # For OS files, we rely on on_result of a hidden picker or page.on_file_drop
        pass

    # Better: Use page.on_file_drop for OS files
    def on_file_drop(e: ft.FilePickerResultEvent):
        # e.files is list of paths (if native). 
        # Actually Flet native DragFiles event.
        pass

    # Correct Flet App Drag Drop
    def window_event(e):
        if e.data == "close":
            page.window.close()
            
    page.window.prevent_close = True
    page.window.on_event = window_event

    # Native File Drop
    def on_files_dropped(e: ft.FileDropEvent):
        if e.files:
            # Take the first folder or parent of first file
            fpath = e.files[0].path
            if os.path.isfile(fpath):
                fpath = os.path.dirname(fpath)
            dashboard.txt_path.value = fpath
            dashboard.add_log(f"Carpeta detectada (Drag&Drop): {fpath}")
            page.update()
            
    page.on_file_drop = on_files_dropped

    # Initialize FilePicker (Native)
    folder_picker = ft.FilePicker(on_result=lambda e: dashboard.txt_path.__setattr__("value", e.path) if e.path else None or page.update())
    page.overlay.append(folder_picker)
    dashboard.set_file_picker(folder_picker)

    page.add(dashboard)

if __name__ == "__main__":
    print("--- INICIANDO COMMANDER UI (WEB MODE) ---")
    print("Se abrirá en tu navegador predeterminado...")
    ft.app(target=main, view=ft.WEB_BROWSER)
