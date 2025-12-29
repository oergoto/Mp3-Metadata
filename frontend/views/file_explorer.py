import flet as ft
import os

class FileExplorerDialog(ft.AlertDialog):
    def __init__(self, page: ft.Page, on_result, initial_path=None, title="Seleccionar Carpeta"):
        self.page_ref = page
        self.on_result = on_result
        self.current_path = initial_path if initial_path and os.path.exists(initial_path) else os.path.expanduser("~")
        
        # UI Elements
        self.txt_path = ft.Text(self.current_path, size=12, font_family="Roboto Mono", color=ft.Colors.CYAN_100)
        self.lv_files = ft.ListView(expand=True, spacing=2, height=300)
        
        super().__init__(
            modal=True,
            title=ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(self.txt_path, bgcolor=ft.Colors.BLACK54, padding=8, border_radius=4),
                    ft.Divider(height=10, color="transparent"),
                    ft.Container(
                        content=self.lv_files,
                        border=ft.border.all(1, ft.Colors.GREY_900),
                        border_radius=4,
                        padding=5,
                        height=300,
                        bgcolor="#121212"
                    )
                ], width=500),
                height=350,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=self._cancel, style=ft.ButtonStyle(color=ft.Colors.RED_ACCENT)),
                ft.ElevatedButton("Seleccionar", on_click=self._select, bgcolor=ft.Colors.CYAN_700, color="white"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=4),
            bgcolor="#1E1E1E" # Card background
        )
        
        self._refresh_list()

    def _refresh_list(self):
        self.lv_files.controls.clear()
        self.txt_path.value = self.current_path
        
        try:
            # ".." Item
            parent = os.path.dirname(self.current_path)
            if parent and parent != self.current_path:
                 self.lv_files.controls.append(
                    self._create_item(".. (Subir nivel)", parent, is_up=True)
                )

            # List dirs and files
            items = sorted(os.listdir(self.current_path))
            dirs = []
            files = []
            for item in items:
                if item.startswith("."): continue
                full_path = os.path.join(self.current_path, item)
                if os.path.isdir(full_path):
                    dirs.append((item, full_path))
                else:
                    files.append((item, full_path))
            
            # Add Dirs
            for name, path in dirs:
                self.lv_files.controls.append(self._create_item(name, path, is_dir=True))
                
            # Add Files
            for name, path in files:
                if name.lower().endswith((".mp3", ".flac", ".wav", ".m4a", ".aiff")):
                    self.lv_files.controls.append(self._create_item(name, path, is_dir=False))
                    
        except PermissionError:
             self.lv_files.controls.append(ft.Text("⚠ Acceso Denegado", color="red"))
        except Exception as e:
             self.lv_files.controls.append(ft.Text(f"Error: {e}", color="red"))
             
        if self.page:
            self.update()

    def _create_item(self, name, path, is_up=False, is_dir=True):
        if is_up:
            icon = ft.Icons.FOLDER_OPEN
            color = ft.Colors.BLUE_200
            on_click = lambda e: self._navigate(path)
        elif is_dir:
            icon = ft.Icons.FOLDER
            color = ft.Colors.AMBER
            on_click = lambda e: self._navigate(path)
        else:
            icon = ft.Icons.AUDIO_FILE
            color = ft.Colors.CYAN_100
            on_click = None # File selection logic could go here
        
        return ft.ListTile(
            leading=ft.Icon(icon, color=color, size=20),
            title=ft.Text(name, size=13, color="#E0E0E0" if not is_dir else "#FFFFFF"),
            dense=True,
            on_click=on_click,
            hover_color=ft.Colors.WHITE10
        )

    def _navigate(self, path):
        self.current_path = path
        self._refresh_list()

    def _select(self, e):
        self.on_result(self.current_path)
        self.open = False
        self.page_ref.update()

    def _cancel(self, e):
        self.open = False
        self.page_ref.update()
