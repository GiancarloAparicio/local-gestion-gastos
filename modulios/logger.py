"""Módulo de logging centralizado para el sistema local-gestion-gastos.

Proporciona funcionalidad de logging estructurado que escribe en un archivo
y también output a consola. Diseñado para funcionar en Termux/Linux con
permisos restringidos (solo propietario).
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Configuración por defecto
DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "app.log"
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColoredFormatter(logging.Formatter):
    """Formato de log con colores para consola."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m',       # Reset
    }
    
    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created).strftime(datefmt) if datefmt else datetime.fromtimestamp(record.created).isoformat()
    
    def formatMessage(self, record):
        result = super().formatMessage(record)
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.COLORS['RESET'])
        return f"{color}{levelname:<8}{self.COLORS['RESET']} {result}"


def setup_logger(
    name: str = "local_gestion_gastos",
    log_file: Path = DEFAULT_LOG_FILE,
    level: int = DEFAULT_LOG_LEVEL,
    format_str: str = DEFAULT_LOG_FORMAT,
    datefmt: str = DATE_FORMAT,
) -> logging.Logger:
    """Configura y retorna un logger con archivo y consola."""
    
    # Asegurar que el directorio de logs exista
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Si no podemos crear el directorio, intentar en el directorio actual
        log_file = Path("./logs_app.log")
    
    # Crear logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar propagación a root logger para evitar duplicados
    logger.propagate = False
    
    # Limpiar handlers existentes
    logger.handlers = []
    
    # Handler de archivo (siempre escritura)
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(format_str, datefmt)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except (PermissionError, FileNotFoundError) as e:
        print(f"⚠️ No se pudo crear archivo de log: {e}")
    
    # Handler de consola (solo si es TTY)
    if sys.stdout.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(format_str, datefmt)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


# Instanciar el logger por defecto al importar
logger = setup_logger()

# Funciones de conveniencia
def info(msg, *args, **kwargs):
    """Registrar mensaje INFO."""
    logger.info(msg, *args, **kwargs)

def debug(msg, *args, **kwargs):
    """Registrar mensaje DEBUG."""
    logger.debug(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """Registrar mensaje WARNING."""
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """Registrar mensaje ERROR."""
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    """Registrar mensaje CRITICAL."""
    logger.critical(msg, *args, **kwargs)


def log_step(step_num: int, total: int, accion: str, detalles: dict = None):
    """Formato especial para pasos de procesamiento."""
    msg = f"PASO {step_num:02d}/{total:02d} - {accion}"
    if detalles:
        detalle_str = " | ".join([f"{k}={v}" for k, v in detalles.items()])
        msg += f" | {detalle_str}"
    info(msg)


def log_transaccion(titulo: str, datos: dict):
    """Formato especial para registro de transacciones."""
    campos_esenciales = [
        f"monto={datos.get('monto', 'N/A')}",
        f"destinatario={datos.get('destinatario', 'N/A')}",
        f"tipo={datos.get('tipo', 'N/A')}",
        f"motivo={datos.get('motivo', 'N/A')[:20] if datos.get('motivo') else 'N/A'}",
    ]
    info(f"{titulo} | {' | '.join(campos_esenciales)}")
