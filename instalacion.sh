#!/bin/bash
# ============================================================
# Script de Instalación Completa: local-gestion-gastos
# ============================================================

echo "============================================================"
echo "Instalando local-gestion-gastos con entorno virtual"
echo "============================================================"
echo ""

# 1. Verificar Python3
echo "[1/7] Verificando Python3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 no encontrado. Instalando..."
    if [ -f "/data/data/com.termux/files/usr/bin/pkg" ]; then
        pkg install -y python python-pip
    else
        echo "❌ No se pudo instalar Python3 automáticamente."
        exit 1
    fi
fi
echo "✅ Python3 $(python3 --version)"
echo ""

# 2. Crear entorno virtual
echo "[2/7] Creando entorno virtual de Python..."
PROJECT_DIR="$HOME/local-gestion-gastos"
VENV_DIR="$PROJECT_DIR/.venv"

if [ -d "$VENV_DIR" ]; then
    echo "⚠️ Entorno virtual ya existe en $VENV_DIR"
    read -p "¿Desea recrearlo? (y/n): " recrear
    if [ "$recrear" = "y" ]; then
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "✅ Entorno virtual creado en $VENV_DIR"
fi

# Activar entorno virtual
echo ""
echo "[3/7] Activando entorno virtual..."
source "$VENV_DIR/bin/activate"
echo "✅ Entorno virtual activado"

# 4. Instalar dependencias desde requirements.txt
echo "[4/7] Instalando dependencias..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip install -r "$PROJECT_DIR/requirements.txt"
    echo "✅ Dependencias instaladas desde $PROJECT_DIR/requirements.txt"
else
    echo "⚠️ Archivo requirements.txt no encontrado"
fi
echo ""

# 5. Copiar estructura del proyecto si no existe
echo "[5/7] Copiando estructura del proyecto..."
if [ ! -f "$PROJECT_DIR/adaptadores/ibk.py" ]; then
    cp -r /home/giancarlo/local-gestion-gastos/* "$PROJECT_DIR"/ 2>/dev/null && echo "✅ Archivos copiados" || echo "⚠️ Algunos archivos no pudieron copiarse"
else
    echo "✅ Estructura del proyecto ya existe en $PROJECT_DIR"
fi
echo ""

# 6. Configurar variables de entorno
echo "[6/7] Configurando variables de entorno..."
cat >> "$HOME/.bashrc" << 'EOF_EXTERNO'

# ============================================================
# Configuración de local-gestion-gastos
# ============================================================

export LOCAL_GASTOS_DIR="$HOME/local-gestion-gastos"
export PATH="$PROJECT_DIR/.venv/bin:$PATH"

if [ -f "$LOCAL_GASTOS_DIR/modulios/termux_api.py" ]; then
    echo "✅ local-gestion-gastos configurado directorio: $LOCAL_GASTOS_DIR"
    echo "   Entorno virtual: $LOCAL_GASTOS_DIR/.venv"
fi
EOF_EXTERNO
source "$HOME/.bashrc" 2>/dev/null || true
echo "✅ Variables de entorno configuradas"
echo ""

# 7. Verificar importaciones críticas
echo "[7/7] Verificando importaciones críticas..."
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/modulios')
sys.path.insert(0, '$PROJECT_DIR/adaptadores')

import re, uuid, time, json, sqlite3, logging
print('✅ Módulos básicos del sistema OK')

from adaptadores.ibk import IBKAdapter
adapter = IBKAdapter()
print('✅ IBKAdapter inicializado correctamente')

test_msgs = [
    'TRAN S/ 98.00\nA: Brithney Castillon',
    'Plineaste S/ 98.00 a Brithney Castillon',
    'Realizaste un consumo con tu tarjeta.',
    'S/ 63.67 con Infinite ••9820'
]
for msg in test_msgs:
    fmt = adapter._clasificar_formato(msg)
    print(f'   Formato {test_msgs.index(msg)+1}: {fmt}')
"
echo ""

echo "============================================================"
echo "¡Instalación y configuración completadas!"
echo "============================================================"
echo "Ubicación del proyecto: $PROJECT_DIR"
echo "Entorno virtual: $PROJECT_DIR/.venv"
echo "Para activar: source $PROJECT_DIR/.venv/bin/activate"
echo "Para usar: source \$HOME/.bashrc && python3"
echo "============================================================"
# 5. Crear base de datos y tablas SQLite usando SQLiteAdapter
echo "[5/7] Creando base de datos y tablas SQLite..."
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/adaptadores')
from adaptadores.infraestructura.sqlite_adapter import SQLiteAdapter
adapter = SQLiteAdapter('$PROJECT_DIR/local_gastos.db')
adapter._inicializar_bd()
print('✅ Base de datos y tablas creadas')
"
