"""Módulo de logging centralizado para el sistema local-gestion-gastos.

Proporciona funcionalidad de logging estructurado que escribe en un archivo
y también output a consola. Diseñado para funcionar en Termux/Linux con
permisos restringidos (solo propietario). Lee la configuración de archivo
del archivo config.yaml.

Ejemplo de uso:
    from modulios.logger import setup_logger, info, warning, error
    info("Sistema iniciado")
"""

import logging
import logging.handlers
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path


def _parsear_bytes(valor) -> int:
    """Convierte '10 MB', '500 KB', '1 GB' o '0' a bytes. 0 = sin rotación."""
    if valor is None:
        return 0
    texto = str(valor).strip().upper()
    if texto in ("", "0", "NONE", "OFF"):
        return 0
    numero = "".join(c for c in texto if c.isdigit() or c == ".")
    multiplicador = 1
    if "KB" in texto:
        multiplicador = 1024
    elif "MB" in texto:
        multiplicador = 1024 ** 2
    elif "GB" in texto:
        multiplicador = 1024 ** 3
    try:
        return int(float(numero) * multiplicador)
    except (TypeError, ValueError):
        return 0

# Cargar configuración de logging desde config.yaml
RUTA_CONFIG = Path(__file__).parent.parent / "config.yaml"
try:
    with open(RUTA_CONFIG, 'r', encoding='utf-8') as f:
        config_yaml = yaml.safe_load(f)
    LOG_CONFIG = config_yaml.get('logging', {}) if config_yaml else {}
    LOG_LEVEL = getattr(logging, LOG_CONFIG.get('nivel', 'INFO'), logging.INFO)
    LOG_ARCHIVO = Path(LOG_CONFIG.get('archivo', './logs/app.log'))
    LOG_FORMAT_STR = LOG_CONFIG.get('format', "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG_DATE_FORMAT = LOG_CONFIG.get('datefmt', "%Y-%m-%d %H:%M:%S")
except Exception:
    # Fallbacks si config.yaml no está disponible
    LOG_CONFIG = {}
    LOG_LEVEL = logging.INFO
    LOG_ARCHIVO = Path("./logs/app.log")
    LOG_FORMAT_STR = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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
    log_file: Path = None,
    level: int = None,
    format_str: str = None,
    datefmt: str = None) -> logging.Logger:
    """Configura y retorna un logger con archivo y consola.
    
    Si no se proporcionan parámetros, usa la configuración de config.yaml.
    """
    # Usar configuración por defecto si no se proporcionan argumentos
    if log_file is None:
        log_file = LOG_ARCHIVO
    if level is None:
        level = LOG_LEVEL
    if format_str is None:
        format_str = LOG_FORMAT_STR
    if datefmt is None:
        datefmt = LOG_DATE_FORMAT
    
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
    
    # Handler de archivo (con rotación según config.yaml → logging.rotacion)
    try:
        max_bytes = _parsear_bytes(LOG_CONFIG.get('rotacion', 0))
        if max_bytes > 0:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=3, encoding='utf-8'
            )
        else:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(format_str, datefmt))
        logger.addHandler(file_handler)
    except (PermissionError, FileNotFoundError) as e:
        print(f"⚠️ No se pudo crear archivo de log: {e}")

    # Handler de consola (siempre, para ver el progreso)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter(format_str, datefmt))
    logger.addHandler(console_handler)

    return logger


# Instanciar el logger por defecto al importar
# Usará la ruta de archivo desde config.yaml
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
