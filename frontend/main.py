import flet as ft
import sys
import os
import threading
import time

# --- Setup Paths to import Backend ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.append(os.path.join(PROJECT_ROOT, "backend"))

# from mp3_autotagger.core.manager import LibraryManager (Movido dentro de la función para evitar bloqueo de inicio)

# --- Global State ---
scan_running = False
scan_target_path = ""
scan_results = []
scan_log = []

def main(page: ft.Page):
    page.title = "Mp3 Metadata Professional"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1200
    page.window.height = 800
    page.padding = 20

    # --- UI Components References ---
    # Log View
    log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
    
    # Progress
    progress_bar = ft.ProgressBar(width=400, color="amber", bgcolor="#222222", visible=False)
    status_text = ft.Text("Ready", size=12, color=ft.Colors.GREY_400)

    # Config Inputs
    # Nota: En modo Navegador, el FilePicker no devuelve rutas absolutas por seguridad.
    # Por eso habilitamos la entrada manual.
    txt_path = ft.TextField(
        label="Ruta de la Carpeta (Pega aquí la ruta completa)", 
        hint_text="Ej: /Users/omarem4/Music/MyFolder",
        width=500, 
        read_only=False
    )
    
    # Flags
    chk_dry_run = ft.Checkbox(label="Dry Run (Simulación)", value=True)
    chk_discogs = ft.Checkbox(label="Usar Discogs", value=True)
    chk_strict = ft.Checkbox(label="Modo Estricto (90% Confianza)", value=True)

    # Stats
    stat_processed = ft.Text("0", size=30, weight=ft.FontWeight.BOLD)
    stat_match = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN)
    stat_error = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.RED)

    # --- Logic ---

    def log_message(msg: str):
        log_list.controls.append(ft.Text(f"> {msg}", font_family="Consolas", size=12))
        page.update()

    def pick_folder_result(e: ft.FilePickerResultEvent):
        if e.path:
            txt_path.value = e.path
            log_message(f"Carpeta seleccionada: {e.path}")
            page.update()

    # Flet 0.25.2 Style
    folder_picker = ft.FilePicker(on_result=pick_folder_result)
    page.overlay.append(folder_picker)

    def start_scan(e):
        global scan_running
        if scan_running:
            return

        # Sanitize input (remove quotes if user pasted specific format)
        raw_path = txt_path.value.strip()
        if (raw_path.startswith('"') and raw_path.endswith('"')) or (raw_path.startswith("'") and raw_path.endswith("'")):
            raw_path = raw_path[1:-1]
            
        if not raw_path:
            log_message("ERROR: Ingresa una ruta primero.")
            return
            
        if not os.path.exists(raw_path):
             log_message(f"ERROR: La ruta no existe: {raw_path}")
             return

        scan_running = True
        btn_scan.disabled = True
        progress_bar.visible = True
        log_list.controls.clear()
        data_table.rows.clear()
        
        # Reset Stats
        stat_processed.value = "0"
        stat_match.value = "0"
        stat_error.value = "0"
        
        # Switch to logs tab initially
        tabs.selected_index = 0
        
        log_message("=== INICIANDO ESCANEO ===")
        log_message(f"Target: {txt_path.value}")
        log_message(f"Config: DryRun={chk_dry_run.value}, Discogs={chk_discogs.value}")
        page.update()

        # Run in Thread
        t = threading.Thread(target=run_backend_logic, args=(raw_path, chk_dry_run.value, chk_discogs.value))
        t.start()

    def run_backend_logic(path, is_dry, use_discogs):
        global scan_running
        
        # --- UI Callback ---
        def on_progress(msg, idx, total, stats, details=None):
            # Update Log
            log_list.controls.append(ft.Text(f"> {msg}", font_family="Consolas", size=12))
            
            # Update Stats
            stat_processed.value = str(stats["processed"])
            stat_match.value = str(stats["matched"])
            stat_error.value = str(stats["failed"])
            
            # Add to Table if details provided
            if details:
                row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text("✅ MATCH", color=ft.Colors.GREEN)),
                        ft.DataCell(ft.Text(details.get("artist", "")[:30])), # Truncate for display
                        ft.DataCell(ft.Text(details.get("title", "")[:30])),
                        ft.DataCell(ft.Text(f"{details.get('confidence', 0):.2f}%")),
                        ft.DataCell(ft.Text(f"{details.get('duration_diff', 0.0)}s", color="red" if abs(details.get('duration_diff', 0)) > 5 else "white")),
                    ]
                )
                data_table.rows.append(row)
                
            # Auto-scroll Logs
            log_list.scroll_to(offset=-1, duration=300)
            
            try:
                page.update()
            except:
                pass

        try:
             # Lazy Import para no bloquear la UI al inicio
             from mp3_autotagger.core.manager import LibraryManager
             
             # Connect to Manager Logic
             manager = LibraryManager(use_discogs=use_discogs, dry_run=is_dry, progress_callback=on_progress)
             
             log_message("Procesando biblioteca... ")
             
             # Dummy Output for prototype (can be changed by user later)
             output_path = os.path.join(path, "clean_output_flet")
             if is_dry:
                 output_path = path 
             
             manager.process_library(path, output_path)
             
             log_message("--- PROCESO TERMINADO ---")
             log_message(f"Procesados: {manager.stats['processed']}")
             log_message(f"Matches: {manager.stats['matched']}")

             
        except Exception as e:
            log_message(f"ERROR CRÍTICO: {e}")
        finally:
            scan_running = False
            btn_scan.disabled = False
            progress_bar.visible = False
            page.update()


    # --- Layout ---
    
    header = ft.Row(
        [
            ft.Icon(ft.Icons.ALBUM, size=40, color="amber"),
            ft.Text("Mp3 Metadata: Professional Tagger", size=24, weight=ft.FontWeight.BOLD)
        ],
        alignment=ft.MainAxisAlignment.CENTER
    )

    config_section = ft.Container(
        content=ft.Column([
            ft.Text("Configuración", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                txt_path,
                ft.IconButton(ft.Icons.FOLDER_OPEN, on_click=lambda _: folder_picker.get_directory_path()),
            ]),
            ft.Row([chk_dry_run, chk_discogs, chk_strict])
        ]),
        padding=10,
        bgcolor=ft.Colors.WHITE10,
        border_radius=10
    )

    stats_section = ft.Row(
        [
            ft.Column([ft.Text("Procesados"), stat_processed], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Column([ft.Text("Coincidencias"), stat_match], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Column([ft.Text("Fallos"), stat_error], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ],
        alignment=ft.MainAxisAlignment.SPACE_EVENLY
    )

    btn_scan = ft.ElevatedButton(
        "ANALIZAR BIBLIOTECA", 
        icon=ft.Icons.PLAY_ARROW, 
        bgcolor="amber", 
        color="black",
        on_click=start_scan,
        height=50
    )

    # --- Results Table ---
    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Estado")),
            ft.DataColumn(ft.Text("Artista")),
            ft.DataColumn(ft.Text("Título")),
            ft.DataColumn(ft.Text("Confianza")),
            ft.DataColumn(ft.Text("Diff (s)")),
        ],
        rows=[]
    )
    
    tab_logs = ft.Tab(text="Logs de Proceso", content=log_list)
    tab_results = ft.Tab(
        text="Resultados (Tabla)", 
        content=ft.Column([data_table], scroll=ft.ScrollMode.AUTO, expand=True)
    )
    
    tabs = ft.Tabs(
        selected_index=0, 
        animation_duration=300, 
        tabs=[tab_logs, tab_results],
        expand=True
    )

    # Main Grid
    page.add(
        header,
        ft.Divider(),
        config_section,
        ft.Divider(),
        stats_section,
        ft.Divider(),
        btn_scan,
        progress_bar,
        status_text,
        ft.Container(
            content=tabs,
            expand=True,
            bgcolor=ft.Colors.BLACK,
            border_radius=5,
            padding=10
        )
    )

if __name__ == "__main__":
    print("--- INICIANDO APP MP3 METADATA ---")
    print("Intentando abrir en el navegador web...")
    # Forzamos modo navegador para evitar problemas de ventana nativa
    ft.app(target=main, view=ft.WEB_BROWSER)
