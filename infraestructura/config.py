"""Carga centralizada de configuración.

Única fuente de verdad para resolver rutas y valores desde config.yaml.
Todas las abstracciones (input, gps, database, notification) usan este módulo
para que Termux y Linux compartan exactamente la misma configuración.
"""

import os
import yaml

# Raíz del proyecto (directorio que contiene config.yaml)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUTA_CONFIG = os.path.join(RAIZ, "config.yaml")

# Caché de configuración para no leer el archivo en cada llamada
_config_cache = None


def cargar_config() -> dict:
    """Lee config.yaml y lo retorna como diccionario. Nunca lanza excepción."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    try:
        with open(_RUTA_CONFIG, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError, OSError):
        _config_cache = {}
    return _config_cache


def valor(*claves, default=None):
    """Obtiene un valor anidado desde config.yaml.

    Ejemplo: valor("bd", "ruta_sqlite", default="./local_gastos.db")
    """
    actual = cargar_config()
    for clave in claves:
        if isinstance(actual, dict) and clave in actual:
            actual = actual[clave]
        else:
            return default
    return actual if actual is not None else default


def es_termux() -> bool:
    """Detecta si se ejecuta dentro de Termux (Android)."""
    señales = ("ANDROID_DATA", "EXTERNAL_STORAGE", "com.termux", "TERMUX_VERSION")
    return any(s in os.environ for s in señales)


def entorno() -> str:
    """Retorna 'termux' o 'linux'."""
    return "termux" if es_termux() else "linux"


def resolver_ruta(ruta: str) -> str:
    """Convierte una ruta relativa (de config.yaml) en absoluta respecto a la raíz."""
    if not ruta:
        return os.path.join(RAIZ, "local_gastos.db")
    if os.path.isabs(ruta):
        return ruta
    return os.path.normpath(os.path.join(RAIZ, ruta))


def ruta_db() -> str:
    """Ruta absoluta al archivo SQLite configurado en bd.ruta_sqlite."""
    return resolver_ruta(valor("bd", "ruta_sqlite", default="./local_gastos.db"))


def tipo_db() -> str:
    """Tipo de motor de base de datos configurado (sqlite por defecto)."""
    return str(valor("bd", "tipo", default="sqlite")).lower()


def termux_bin() -> str:
    """Ruta de los binarios de Termux configurada en termux.path."""
    return valor("termux", "path", default="/data/data/com.termux/files/usr/bin")


def modo_operacion() -> str:
    """Modo de operación por defecto configurado en config.yaml."""
    modo = valor("modo_operacion", default="automate_broker")
    if modo not in ("automate_broker", "listener_directo"):
        return "automate_broker"
    return modo


def _archivo_configurado() -> str:
    """Lee la ruta del archivo único de notificaciones desde config.yaml.

    Claves nuevas: ``automate_broker.archivo_notificacion``.
    Compatibilidad: ``directorio_archivos`` / ``directorio_archivos_automate``.
    """
    ruta = valor("automate_broker", "archivo_notificacion")
    if not ruta:
        ruta = valor("archivo_notificacion_automate")
    if not ruta:
        ruta = valor("automate_broker", "directorio_archivos")  # legacy
    if not ruta:
        ruta = valor("directorio_archivos_automate")  # legacy
    return str(ruta) if ruta else ""


def archivo_notificacion() -> str:
    """Ruta del ÚNICO archivo de notificación que Automate reescribe.

    - Termux: usa la ruta configurada (p. ej. ``.../Documents/noti.json``).
    - Linux: usa ``<proyecto>/noti_inbox/noti.json``.
    """
    if es_termux():
        ruta = _archivo_configurado()
        if ruta:
            return ruta
    return os.path.join(RAIZ, "noti_inbox", "noti.json")


def ventana_consolidacion_minutos() -> int:
    """Minutos de la ventana de consolidación."""
    try:
        return int(valor("ventana_consolidacion", "minutos", default=5))
    except (TypeError, ValueError):
        return 5


def timeout_gps() -> int:
    """Segundos de espera para GPS."""
    try:
        return int(valor("procesamiento", "tiempo_espera_gps_segundos", default=10))
    except (TypeError, ValueError):
        return 10


def timeout_dialogo() -> int:
    """Segundos de espera para diálogos."""
    try:
        return int(valor("procesamiento", "tiempo_espera_dialogo_segundos", default=30))
    except (TypeError, ValueError):
        return 30


def mapeo_adaptadores() -> dict:
    """Mapeo paquete Android -> nombre corto de adaptador."""
    mapeo = valor("mapeo_adaptadores", default={})
    return mapeo if isinstance(mapeo, dict) else {}


def adaptadores_activos() -> list:
    """Lista de adaptadores activos configurados."""
    activos = valor("adaptadores_activos", default=[])
    return activos if isinstance(activos, list) else []
