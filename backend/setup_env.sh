#!/bin/bash

# Script de Configuración Automática del Entorno
# Ejecutar con: bash setup_env.sh

echo "=== Configurando Entorno Mp3 Metadata ==="

# 1. Limpiar entorno anterior si existe
if [ -d ".venv" ]; then
    echo "[INFO] Eliminando entorno virtual anterior (.venv)..."
    rm -rf .venv
fi

# 2. Crear nuevo entorno virtual
echo "[INFO] Creando nuevo entorno virtual (python3 -m venv .venv)..."
python3 -m venv .venv

# 3. Activar e instalar dependencias
echo "[INFO] Activando e instalando dependencias..."
source .venv/bin/activate

# Actualizar pip
python3 -m pip install --upgrade pip

# Instalar requerimientos
if [ -f "requirements.txt" ]; then
    echo "[INFO] Instalando librerías desde requirements.txt..."
    python3 -m pip install -r requirements.txt
else
    echo "[ERROR] No se encontró requirements.txt"
    exit 1
fi

echo ""
echo "=== Instalación Completa ==="
echo "Para activar el entorno y usar el programa, ejecuta:"
echo ""
echo "source .venv/bin/activate"
echo "python3 main.py --help"
echo ""
