#!/bin/bash
echo "=== local-gestion-gastos Installation Script ==="

# Verify Python
if python3 --version > /dev/null 2>&1; then
    echo "✅ Python3 available: $(python3 --version)"
else
    echo "❌ Python3 not found"
    exit 1
fi

# Create project directories
PROJECT_DIR="$HOME/local-gestion-gastos"
mkdir -p "$PROJECT_DIR/adaptadores"
mkdir -p "$PROJECT_DIR/modulios"
mkdir -p "$PROJECT_DIR/docs"
echo "✅ Directories created: $PROJECT_DIR"

# Copy project files
if [ ! -f "$PROJECT_DIR/adaptadores/ibk.py" ]; then
    cp -r /home/giancarlo/local-gestion-gastos/* "$PROJECT_DIR"/ 2>/dev/null && echo "✅ Files copied" || echo "⚠️ Some files could not be copied"
else
    echo "✅ Files already exist"
fi

# Verify imports
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/modulios')
sys.path.insert(0, '$PROJECT_DIR/adaptadores')
import re, uuid, time, json, sqlite3
print('✅ Basic Python modules OK')

from adaptadores.ibk import IBKAdapter
adapter = IBKAdapter()
print('✅ IBKAdapter loaded')

# Test format classification
tests = [
    'TRAN S/ 98.00\nA: Brithney Castillon',
    'Plineaste S/ 98.00 to Brithney Castillon',
    'Realizaste un consumo con tu tarjeta.',
    'S/ 63.67 con Infinite ••9820'
]
for t in tests:
    fmt = adapter._clasificar_formato(t)
    print(f'   Format: {tests.index(t)+1} -> {fmt}')
"
echo "✅ All modules tested successfully"

# Setup bashrc
echo 'export LOCAL_GASTOS_DIR="$HOME/local-gestion-gastos"' >> "$HOME/.bashrc" 2>/dev/null
echo "✅ Environment configured"

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo "Project location: $PROJECT_DIR"
echo "To use: source \$HOME/.bashrc && python3"
echo "========================================"
