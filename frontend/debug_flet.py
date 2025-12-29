import flet as ft
import sys
import os

print(f"Python Executable: {sys.executable}")
print("DEBUG: Importing Flet success")

def main(page: ft.Page):
    print("DEBUG: Inside Main")
    page.title = "Debug App"
    page.add(ft.Text("Si ves esto, Flet funciona basico."))
    print("DEBUG: Widget added")

if __name__ == "__main__":
    print("DEBUG: Starting App (WEB BROWSER MODE)")
    try:
        # Force browser to bypass native window issues
        ft.app(target=main, view=ft.WEB_BROWSER)
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
