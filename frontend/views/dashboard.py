import flet as ft
import os
from typing import Dict, Any
from .file_explorer import FileExplorerDialog

class DashboardView(ft.Container):
    def __init__(self, page: ft.Page, on_start_scan, on_commit, on_export_csv):
        super().__init__()
        self.page = page
        self.on_start_scan = on_start_scan
        self.on_commit = on_commit
        self.on_export_csv = on_export_csv
        self.expand = True
        
        # --- State ---
        self.scan_results = [] 
        self.selected_indices = set()
        
        # Column Config (Key -> Label)
        self.all_columns = {
            "status": "Estado",
            "cover_path": "Art", # New Column
            "title": "Título",
            "artist": "Artista",
            "original_filename": "Archivo Original",
            "duration_str": "Duración",
            "duration_diff": "Diff (s)",
            "genre": "Género",
            "styles": "Estilos",
            "source": "Fuente",
            "confidence": "Confiabilidad",
            "publisher": "Sello (Label)",
            "cat_number": "Cat. Number",
            "year": "Año",
            "country": "País",
            "format": "Formato",
            "release_type": "Tipo Release",
            "release_status": "Status Release",
            "isrc": "ISRC",
            "mb_track_id": "MB Track ID",
            "url_spotify": "Link Spotify",
            "url_discogs": "Link Discogs"
        }
        
        # Default Visible Columns (User Preference)
        self.visible_columns = [
            "status", "cover_path", "title", "artist", "original_filename", 
            "duration_str", "duration_diff", "genre", "styles", 
            "source", "confidence"
        ]
        
        # --- Components ---
        self._build_components()
        self.content = self._build_layout()

    def _build_components(self):
        # 1. KPIs (Value Controllers)
        self.stat_processed = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#FFFFFF", font_family="Roboto Mono")
        self.stat_match = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#00E676", font_family="Roboto Mono") # Green Accent
        self.stat_rescued = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#FFEA00", font_family="Roboto Mono") # Amber
        self.stat_rejected = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#FF1744", font_family="Roboto Mono") # Red
        
        # 2. Controls
        self.txt_path = ft.TextField(
            hint_text="Music Library Path...",
            border=ft.InputBorder.NONE,
            color="#FFFFFF",
            text_size=13,
            content_padding=10,
            expand=True,
            text_style=ft.TextStyle(font_family="Roboto")
        )
        self.btn_pick = ft.IconButton(
            ft.Icons.FOLDER_OPEN, 
            on_click=self._open_file_explorer,
            tooltip="Browse",
            icon_color="#2979FF", # Electric Blue
        )
        
        # Toggles (Styled closer to RB7 buttons? Using Switch for now but cleaner)
        self.chk_dry_run = ft.Switch(label="DRY RUN", value=True, active_color="#FF9800", label_style=ft.TextStyle(size=11, color="#AAAAAA"))
        self.chk_discogs = ft.Switch(label="DISCOGS", value=True, active_color="#2979FF", label_style=ft.TextStyle(size=11, color="#AAAAAA"))
        self.chk_strict = ft.Switch(label="STRICT", value=True, active_color="#D50000", label_style=ft.TextStyle(size=11, color="#AAAAAA"))
        
        self.btn_scan = ft.ElevatedButton(
            "SCAN", 
            icon=ft.Icons.SEARCH, 
            bgcolor="#2979FF", 
            color="white",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=2)),
            on_click=self._handle_scan,
        )

        self.btn_commit = ft.ElevatedButton(
            "COMMIT", 
            icon=ft.Icons.SAVE_ALT, 
            bgcolor="#D32F2F", 
            color="white",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=2)),
            on_click=self._handle_commit,
            disabled=True,
        )
        
        self.btn_export = ft.OutlinedButton(
             "EXPORT",
             icon=ft.Icons.DOWNLOAD,
             icon_color="#00E676",
             style=ft.ButtonStyle(
                 shape=ft.RoundedRectangleBorder(radius=2), 
                 side=ft.BorderSide(1, "#00E676"),
                 color={ft.ControlState.DEFAULT: "#00E676", ft.ControlState.DISABLED: ft.Colors.GREY_700}
             ),
             on_click=self._handle_export,
             disabled=True
        )
        
        # Column Selector
        self.btn_columns = ft.PopupMenuButton(
            icon=ft.Icons.VIEW_COLUMN,
            tooltip="Columns",
            icon_color="#AAAAAA",
            items=[
                ft.PopupMenuItem(
                    text=label,
                    checked=(key in self.visible_columns),
                    on_click=lambda e, k=key: self._toggle_column(k)
                ) for key, label in self.all_columns.items()
            ]
        )
        
        # 3. DataGrid (Rekordbox Browser Style)
        self.data_table = ft.DataTable(
            columns=self._build_columns(),
            rows=[],
            # Minimalist Borders
            border=ft.border.all(0, "transparent"),
            vertical_lines=ft.border.BorderSide(0, "transparent"),
            horizontal_lines=ft.border.BorderSide(1, "#1A1A1A"), # Very subtle divider
            heading_row_color="#111111",
            heading_row_height=35,
            data_row_max_height=40, # Dense
            heading_text_style=ft.TextStyle(font_family="Roboto", weight=ft.FontWeight.BOLD, size=11, color="#AAAAAA"),
            data_row_color={"hovered": "#0D47A1"}, # Selection color
            column_spacing=15,
            show_checkbox_column=True, # Adding native selection? No time to re-wire. Keeping custom logic.
        )
        
        # Logs
        self.log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    def _build_columns(self):
        return [ft.DataColumn(ft.Text(self.all_columns[key])) for key in self.visible_columns]

    def _toggle_column(self, key):
        if key in self.visible_columns:
            self.visible_columns.remove(key)
        else:
            # Maintain order based on all_columns keys
            new_list = []
            for k in self.all_columns.keys():
                if k == key or k in self.visible_columns:
                    new_list.append(k)
            self.visible_columns = new_list
            
        # Update Menu Items Checked State
        for item in self.btn_columns.items:
            # We need to find the item. Text matches label.
            # Using content wrapper might be safer, but iteration is fine
            if item.text == self.all_columns[key]:
                item.checked = key in self.visible_columns
                
        self._refresh_table()
        self.page.update()

    def _refresh_table(self):
        self.data_table.columns = self._build_columns()
        self.data_table.rows.clear()
        for idx, details in enumerate(self.scan_results):
            self.data_table.rows.append(self._create_row(details))

    def _create_row(self, details: Dict[str, Any]):
        idx = details.get("index", -1)
        cells = []
        for key in self.visible_columns:
            content = ft.Text("-")
            
            # --- Dedicated Renderers ---
            if key == "status":
                status = "READY"
                bg = ft.Colors.GREEN
                if details.get("confidence", 0) < 50:
                    status = "REJECTED"
                    bg = ft.Colors.RED
                elif details.get("rescued", False):
                    status = "RESCUED"
                    bg = ft.Colors.AMBER
                elif abs(details.get("duration_diff", 0)) > 5.0:
                    status = "STRICT FAIL"
                    bg = ft.Colors.RED
                    
                content = ft.Container(
                    ft.Text(status, size=10, weight=ft.FontWeight.BOLD, color="black"),
                    bgcolor=bg, padding=5, border_radius=4
                )
            elif key == "source":
                icon = ft.Icons.DISC_FULL
                col = ft.Colors.BLUE
                src = details.get("source", "")
                if "Spotify" in src:
                    icon = ft.Icons.MUSIC_NOTE
                    col = ft.Colors.GREEN
                elif "MusicBrainz" in src:
                    icon = ft.Icons.LIBRARY_MUSIC
                    col = ft.Colors.PURPLE
                content = ft.Icon(icon, color=col, size=16, tooltip=src)
            
            elif key == "confidence":
                val = details.get('confidence', 0)
                color = ft.Colors.GREEN if val > 90 else (ft.Colors.AMBER if val > 70 else ft.Colors.RED)
                content = ft.Text(f"{val:.0f}%", size=12, color=color, weight=ft.FontWeight.BOLD)
                
            elif key == "duration_diff":
                diff = details.get("duration_diff", 0.0)
                color = ft.Colors.RED if abs(diff) > 5.0 else ft.Colors.WHITE
                content = ft.Text(f"{diff:+.1f}s", color=color, size=12, weight=ft.FontWeight.BOLD)
                
            elif key == "cover_path":
                path = details.get("cover_path", "")
                if path and os.path.exists(path):
                    content = ft.Container(
                        content=ft.Image(
                            src=path, 
                            width=30, 
                            height=30, 
                            fit=ft.ImageFit.COVER,
                            border_radius=4
                        ),
                        padding=0,
                        on_click=lambda e: self._show_cover_preview(path) # Future expansion
                    )
                else:
                     content = ft.Icon(ft.Icons.ALBUM, color=ft.Colors.GREY_800, size=20)
                
            elif key.startswith("url_"):
                # Clickable Links
                url = details.get(key, "")
                if url:
                    content = ft.TextButton("Abrir", url=f"https://{url}" if not url.startswith("http") else url, height=20)
                else:
                    content = ft.Text("-")
            
            else:
                # Generic Text
                val = str(details.get(key, ""))
                if not val: val = "-"
                # Clean technical text
                content = ft.Text(
                    val[:50], 
                    size=12, 
                    tooltip=val, 
                    overflow=ft.TextOverflow.ELLIPSIS,
                    font_family="Roboto Mono" if key not in ["title", "artist"] else None, # Monospace for tech data
                    color=ft.Colors.GREY_300 if key not in ["title", "artist"] else ft.Colors.WHITE
                )
                
            cells.append(ft.DataCell(content))
            
        return ft.DataRow(
            cells=cells,
            on_select_changed=lambda e: self._toggle_selection(idx, e.control.selected),
            selected=(idx in self.selected_indices)
        )

    def _build_layout(self):
        # --- 1. Status Deck (Top Bar) ---
        def stat_item(label, value_ctrl, color):
            return ft.Container(
                content=ft.Column([
                    ft.Text(label, size=10, color=ft.Colors.GREY_500, font_family="Roboto"),
                    value_ctrl
                ], spacing=2),
                padding=ft.padding.symmetric(horizontal=15, vertical=5)
            )

        status_deck = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.ANALYTICS, color=ft.Colors.CYAN_700),
                    ft.Text("LIBRARY STATUS", weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700, size=12),
                ], width=150),
                stat_item("PROCESSED", self.stat_processed, ft.Colors.WHITE),
                stat_item("MATCHES", self.stat_match, ft.Colors.GREEN_ACCENT),
                stat_item("RESCUED", self.stat_rescued, ft.Colors.AMBER_ACCENT),
                stat_item("FAILED", self.stat_rejected, ft.Colors.RED_ACCENT),
            ], alignment=ft.MainAxisAlignment.START),
            bgcolor="#111111", # Surface color
            padding=5,
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#333333"))
        )

        # --- 2. Control Toolbar ---
        self.progress_bar = ft.ProgressBar(width=None, color="#00E676", bgcolor="#1A1A1A", visible=False, height=2)
        
        toolbar = ft.Container(
            content=ft.Column([
                ft.Row([
                    # Path & Explorer
                    ft.Container(
                        content=ft.Row([
                            self.btn_pick,
                            self.txt_path,
                        ]),
                        expand=True,
                        bgcolor="#000000",
                        border=ft.border.all(1, "#333333"),
                        border_radius=4,
                        padding=2
                    ),
                    ft.VerticalDivider(width=20, color="transparent"),
                    # Toggles (Compact)
                    ft.Row([self.chk_dry_run, self.chk_discogs, self.chk_strict], spacing=5),
                    ft.VerticalDivider(width=20, color="#333333"),
                    # Actions
                    self.btn_scan,
                    self.btn_export, 
                    self.btn_commit
                ]),
                self.progress_bar
            ], spacing=0),
            padding=10,
            bgcolor="#000000"
        )
        
        # --- 3. Browser Area ---
        browser_header = ft.Container(
             content=ft.Row([
                 ft.Text("COLLECTION", size=14, weight=ft.FontWeight.BOLD, color="#2979FF"),
                 ft.Container(expand=True),
                 self.btn_columns
             ]),
             padding=ft.padding.only(left=10, right=10, top=5)
        )

        return ft.Column([
            status_deck,
            toolbar,
            browser_header,
            ft.Column(
                 [self.data_table], 
                 expand=True, 
                 scroll=ft.ScrollMode.ADAPTIVE
            )
        ], expand=True, spacing=0)

    def _open_file_explorer(self, e):
        def on_folder_selected(path):
            self.txt_path.value = path
            self.txt_path.update()
            
        dialog = FileExplorerDialog(self.page, on_folder_selected, self.txt_path.value)
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def set_file_picker(self, picker):
        # Native picker ignored in favor of custom dialog
        self.file_picker = picker

    def update_stats(self, processed, matched, rescued, failed):
        self.stat_processed.value = str(processed)
        self.stat_match.value = str(matched)
        self.stat_rescued.value = str(rescued)
        self.stat_rejected.value = str(failed)
        self.page.update()

    def add_log(self, msg):
        self.log_list.controls.append(ft.Text(f"> {msg}", font_family="Consolas", size=11, color=ft.Colors.GREEN_200))
        if len(self.log_list.controls) > 1000:
            self.log_list.controls.pop(0)

    def add_row(self, details: Dict[str, Any]):
        idx = details.get("index", -1)
        self.scan_results.append(details) # Store for refresh
        
        # Optimize: Append only, don't rebuild
        row = self._create_row(details)
        self.data_table.rows.append(row)
        
        # Auto-select if READY/RESCUED logic (optional)
        # User requested stricter confidence. Only > 90% auto-selected.
        if details.get("confidence", 0) >= 90:
             self.selected_indices.add(idx)
             row.selected = True

    def _toggle_selection(self, idx, is_selected):
        if is_selected:
            self.selected_indices.add(idx)
        else:
            self.selected_indices.discard(idx)
            
        # FORCE UI STATE SYNC (Correcting for 1-based index from manager)
        # manager passes 1-based index, DataTable rows are 0-based.
        row_idx = idx - 1
        if 0 <= row_idx < len(self.data_table.rows):
            self.data_table.rows[row_idx].selected = is_selected
        
        self.btn_commit.text = f"COMMIT ({len(self.selected_indices)})"
        self.page.update() # Force full update to ensure checkboxes reflect state

    def _handle_scan(self, e):
        path = self.txt_path.value.strip()
        if not path:
             self.add_log("Error: Ruta vacía")
             self.page.update()
             return
             
        # Clear UI
        self.data_table.rows.clear()
        self.scan_results.clear()
        self.log_list.controls.clear()
        self.selected_indices.clear()
        self.btn_commit.disabled = True
        self.btn_commit.text = "COMMIT"
        self.progress_bar.visible = True 
        self.page.update()
        
        self.on_start_scan(path, self.chk_dry_run.value, self.chk_discogs.value)
        
    def _handle_commit(self, e):
        if not self.selected_indices:
            return
        self.on_commit(list(self.selected_indices))
        
    def _handle_export(self, e):
        if not self.scan_results:
             return
             
        def on_export_path_selected(path):
            self.on_export_csv(self.scan_results, path)
            
        initial_path = os.path.expanduser("~/Downloads")
        if not os.path.exists(initial_path):
            initial_path = os.path.expanduser("~")
            
        dialog = FileExplorerDialog(
            self.page, 
            on_export_path_selected, 
            initial_path,
            title="Seleccionar Carpeta de Destino"
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _show_cover_preview(self, path):
        if not path or not os.path.exists(path):
            return
            
        dlg = ft.AlertDialog(
            content=ft.Image(src=path, fit=ft.ImageFit.CONTAIN, width=400, height=400),
            title=ft.Text("Album Art", weight=ft.FontWeight.BOLD),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.page.close(dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor="#1E1E1E"
        )
        self.page.open(dlg)
        
    def enable_commit(self):
        self.btn_commit.disabled = False
        self.btn_export.disabled = False
        self.btn_commit.text = f"COMMIT ({len(self.selected_indices)})"
        self.progress_bar.visible = False
        self.page.update()
