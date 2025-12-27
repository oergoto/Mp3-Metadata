from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import threading
import asyncio

# Import Core Logic
# Aseguramos que el path de importación funcione
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mp3_autotagger.core.manager import LibraryManager

app = FastAPI(title="Mp3 Metadata API")

# --- Data Models ---
class ScanRequest(BaseModel):
    path: str
    dry_run: bool = True
    use_discogs: bool = True

class ProcessingStatus(BaseModel):
    processed: int
    matched: int
    failed: int
    current_file: str
    is_active: bool

# --- Global State (Simple Memory Store for MVP) ---
# En una app real usaríamos una base de datos o cola de tareas
current_status = ProcessingStatus(processed=0, matched=0, failed=0, current_file="", is_active=False)
manager_instance = None

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Mp3 Metadata Backend is Running"}

@app.post("/api/scan")
async def start_scan(request: ScanRequest):
    global current_status
    
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path does not exist")
    
    if current_status.is_active:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    # Reset status
    current_status = ProcessingStatus(
        processed=0, matched=0, failed=0, 
        current_file="Starting...", is_active=True
    )

    # Launch background task (Thread for now to avoid blocking async loop)
    # En producción idealmente usar Celery o BackgroundTasks de FastAPI
    threading.Thread(target=run_scan_thread, args=(request.path, request.dry_run, request.use_discogs)).start()

    return {"message": "Scan started", "config": request}

@app.get("/api/progress")
def get_progress():
    return current_status

# --- Background Worker ---
def run_scan_thread(path: str, dry_run: bool, use_discogs: bool):
    global current_status, manager_instance
    print(f"[API] Starting scan on {path}")
    
    try:
        # Dummy Output Path for now (UI Flow will handle this later)
        output_path = os.path.join(path, "clean_output_temp")
        
        manager = LibraryManager(use_discogs=use_discogs, dry_run=dry_run)
        
        # NOTE: Necesitamos modificar LibraryManager para que reporte progreso 
        # a nuestra variable global `current_status`. 
        # Por ahora, simularemos que corre (blocking) y luego actualiza.
        # TODO: Implementar Callbacks en LibraryManager.
        
        manager.process_library(path, output_path)
        
        # On Finish
        current_status.is_active = False
        current_status.current_file = "Done"
        current_status.processed = manager.stats["processed"]
        current_status.matched = manager.stats["matched"]
        current_status.failed = manager.stats["failed"]
        
    except Exception as e:
        print(f"[API] Error: {e}")
        current_status.is_active = False
        current_status.current_file = f"Error: {str(e)}"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
