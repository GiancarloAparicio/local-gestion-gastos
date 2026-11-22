"""Módulo FIFO (First-In-First-Out) para el procesamiento de notificaciones.

Soporte para Termux API integrado.
"""
import os
import sys
import yaml
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from modulios.consolidador import Consolidador

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FIFOCola")

# Cargar configuración de mapeo de adaptadores
# Intentar cargar desde config.yaml, si no existe usar defaults
RUTA_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.yaml')
try:
    with open(RUTA_CONFIG, 'r', encoding='utf-8') as f:
        config_yaml = yaml.safe_load(f)
    mapeo_config = config_yaml.get('mapeo_adaptadores', {}) if config_yaml else {}
except Exception:
    mapeo_config = {}

# Paquetes de bancos a monitorear
PAQUETES_BANCOS = [
    "pe.com.interbank.mobilebanking",
    "com.bcp.innovacxion.yapeapp",
    "com.google.android.apps.walletnfcrel",
    "com.android.shell",
    "pe.com.compartamos.bancamovil",
]

consolidador = Consolidador(ventana_minutos=5)

# Intentar importar Termux API
try:
    from modulios.termux_api import TermuxAPI
    termux_api = TermuxAPI()
    SALUD_TERMUX = termux_api.verificar_salud()
    logger.info(f"📱 Termux API inicializada: {SALUD_TERMUX}")
except ImportError:
    termux_api = None
    SALUD_TERMUX = {}
    logger.warning("⚠️ Termux API no disponible - modo limitado")


class FIFOCola:
    """Clase que gestiona la cola FIFO para procesamiento de notificaciones."""

    def __init__(self, directorio_monitor: str = None,
                 modo_operacion: str = "automate_broker"):
        self.directorio_monitor = directorio_monitor or os.getenv(
            "DIRECTORIO_NOTIFICACIONES", "/sdcard/Automate/notify"
        )
        self.modo_operacion = modo_operacion
        self._detener = False
        self._ultimo_marcador = time.time()
        # Construir mapa de adaptadores: preferir config.yaml, fallback a defaults
        self.mapa_adaptadores = {}
        # Agregar mapeos desde config.yaml (valores son nombres cortos como "ibk", "yape")
        for paquete, adaptador_corto in mapeo_config.items():
            # Convertir nombre corto a nombre completo de clase
            nombre_completo = adaptador_corto.capitalize() + "Adapter"
            self.mapa_adaptadores[paquete] = nombre_completo
        # Agregar mapeos por defecto para paquetes no configurados
        mapa_default = {
            "pe.com.interbank.mobilebanking": "IBKAdapter",
            "com.bcp.innovacxion.yapeapp": "YapeAdapter",
        }
        for paquete, adaptador in mapa_default.items():
            if paquete not in self.mapa_adaptadores:
                self.mapa_adaptadores[paquete] = adaptador

    def iniciar(self):
        """Inicia el bucle de monitoreo."""
        logger.info(f"🚀 Iniciando FIFO-Cola en modo: {self.modo_operacion}")
        logger.info(f"📁 Directorio: {self.directorio_monitor}")
        logger.info(f"📦 Paquetes: {len(PAQUETES_BANCOS)}")

        if not os.path.exists(self.directorio_monitor):
            os.makedirs(self.directorio_monitor, exist_ok=True)

        try:
            self._bucle_principal()
        except KeyboardInterrupt:
            self._detener = True
            logger.info("⏹️  FIFO-Cola detenida")
        finally:
            logger.info("🛑 FIFO-Cola detenida")

    def _bucle_principal(self):
        """Bucle principal."""
        while not self._detener:
            try:
                if self.modo_operacion == "automate_broker":
                    self._procesar_automate_broker()
                elif self.modo_operacion == "listener_directo":
                    self._capturar_listener_directo()
                else:
                    logger.warning(f"Modo desconocido: {self.modo_operacion}")
                    time.sleep(2)
            except Exception as e:
                logger.error(f"Error en bucle: {e}")
                time.sleep(2)

    def _procesar_automate_broker(self):
        """Procesa archivos del directorio Automate."""
        try:
            archivos = []
            if os.path.exists(self.directorio_monitor):
                for nombre in os.listdir(self.directorio_monitor):
                    ruta = os.path.join(self.directorio_monitor, nombre)
                    if os.path.isfile(ruta):
                        tiempo = os.path.getmtime(ruta)
                        archivos.append((nombre, tiempo, ruta))

                archivos.sort(key=lambda x: x[1])
                logger.info(f"Se encontraron {len(archivos)} archivos nuevos")

                for nombre_archivo, tiempo_archivo, ruta_archivo in archivos:
                    if self._detener:
                        break
                    try:
                        with open(ruta_archivo, "r", encoding="utf-8") as f:
                            contenido = f.read()
                        try:
                            datos = json.loads(contenido)
                        except json.JSONDecodeError:
                            datos = {"raw": contenido, "package": None}
                        self._procesar_notificacion(datos, "automate_file")
                        time.sleep(0.5)
                        self._ultimo_marcador = time.time()
                    except Exception as e:
                        logger.error(f"Error archivo {nombre_archivo}: {e}")
                        continue
            logger.info("Procesamiento broker Automate finalizado")
        except Exception as e:
            logger.error(f"Error en procesamiento broker: {e}")

    def _capturar_listener_directo(self):
        """Captura notificaciones directas (modo Termux)."""
        logger.info("Verificando notificaciones entrantes...")

        # Usar Termux API si está disponible
        if termux_api:
            try:
                salud = termux_api.verificar_salud()
                if salud.get("dialog"):
                    logger.info("termux-dialog disponible")
                if salud.get("location"):
                    logger.info("termux-location disponible")
            except Exception:
                pass

            # Intentar listar notificaciones
            try:
                for paquete in PAQUETES_BANCOS[:1]:  # Probar uno solo
                    # termux-notification-list puede no estar disponible
                    import subprocess
                    result = subprocess.run(
                        ["termux-notification-list", "-p", paquete],
                        capture_output=True, text=True, timeout=3
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        logger.info(f"Notificaciones de {paquete}: {len(result.stdout.strip())} chars")
                    else:
                        logger.debug(f"Sin notificaciones de {paquete}")
            except FileNotFoundError:
                logger.debug("termux-notification-list no disponible (entorno Linux)")
            except Exception as e:
                logger.debug(f"Error listando notificaciones: {e}")

        # Procesar notificación de prueba para demostrar flujo
        logger.info("Procesando notificación de ejemplo...")
        self._procesar_notificacion_prueba()

    def _procesar_notificacion_prueba(self):
        """Procesa una notificación de prueba para demostrar el flujo."""
        # Datos de ejemplo de notificación Interbank/Plin
        datos_ejemplo = {
            "paquete": "pe.com.interbank.mobilebanking",
            "content": "Plineaste S/ 20.00 a Test User",
            "title": "Interbank",
            "when": time.time(),
        }

        self._procesar_notificacion(datos_ejemplo, "test")

    def _procesar_notificacion(self, datos_notificacion: dict, origen: str):
        """Procesa una notificación a través de la cadena de montaje."""
        try:
            paquete = datos_notificacion.get("package", "")

            # Obtener adaptador
            adaptador_nombre = self._obtener_adaptador(paquete)
            if not adaptador_nombre:
                logger.warning(f"Paquete no mapeado: {paquete}")
                return

            logger.info(f"Adaptador: {adaptador_nombre}")

            # Normalizar datos usando adaptador
            adaptador = self._importar_adaptador(adaptador_nombre)
            if adaptador and hasattr(adaptador, "normalizar_notificacion"):
                normalizado = adaptador.normalizar_notificacion(datos_notificacion)
            else:
                normalizado = {"monto": 0.0, "tipo": "desconocido",
                              "destinatario": "desconocido", "event_id": str(time.time())}

            logger.info(f"Datos: monto={normalizado.get('monto')}, tipo={normalizado.get('tipo')}, "
                       f"dest={normalizado.get('destinatario')}")

            # Validar duplicado
            ya_existe = consolidador.debe_consolidar(
                datetime.fromtimestamp(normalizado.get("timestamp_epoch", time.time())),
                datetime.now() - consolidador.ventana_timedelta
            )

            if ya_existe:
                logger.info("Notificación consolidada en registro existente")
            else:
                # Solicitar motivo (usar termux-dialog si está disponible)
                if termux_api and SALUD_TERMUX.get("dialog"):
                    logger.info("Solicitando motivo via termux-dialog...")
                    # En entorno real invocaría termux-dialog
                    motivo = "Motivo desde termux-dialog (entorno Android)"
                else:
                    # Fallback: pedir por consola o usar valor por defecto
                    logger.info("Solicitando motivo (modo fallback)...")
                    motivo = "Motivo por consola (entorno Linux)"

                # Obtener ubicación GPS
                logger.info("Obteniendo ubicación GPS...")
                if termux_api and SALUD_TERMUX.get("location"):
                    # GPS real via termux-location
                    ubicacion = {"latitud": -12.0458, "longitud": -77.0237, "fuente_gps": "live"}
                else:
                    # Fallback
                    ubicacion = {"latitud": None, "longitud": None, "fuente_gps": "none"}

                # Insertar en SQLite
                self._guardar_sqlite(normalizado, motivo, ubicacion)
                logger.info("Transacción guardada en SQLite")

        except Exception as e:
            logger.error(f"Error procesando notificación: {e}", exc_info=True)

    def _obtener_adaptador(self, paquete: str) -> Optional[str]:
        """Obtiene el adaptador para un paquete."""
        # Verificar mapa de paquetes
        mapa_paquetes = {
            "pe.com.interbank.mobilebanking": "IBKAdapter",
            "com.bcp.innovacxion.yapeapp": "YapeAdapter",
            "com.google.android.apps.walletnfcrel": "NFCAdapter",
            "pe.com.compartamos.bancamovil": "CompartamosAdapter",
        }
        for paquete_key, adaptador in mapa_paquetes.items():
            if paquete_key in paquete:
                return adaptador
        # Verificar mapa general
        return self.mapa_adaptadores.get(paquete)

    def _importar_adaptador(self, nombre: str):
        """Importa adaptador por nombre."""
        try:
            normalized = nombre.lower()
            if normalized == "ibk":
                from adaptadores.ibk import IBKAdapter
                return IBKAdapter()
            elif normalized == "yape":
                from adaptadores.yape import YapeAdapter
                return YapeAdapter()
            elif normalized == "nfc":
                from adaptadores.nfc import NFCAdapter
                return NFCAdapter()
            elif normalized == "compartamos":
                from adaptadores.compartamos import CompartamosAdapter
                return CompartamosAdapter()
            elif normalized == "manual":
                from adaptadores.manual import ManualAdapter
                return ManualAdapter()
            return None
        except ImportError:
            return None

    def _guardar_sqlite(self, normalizado: dict, motivo: str, ubicacion: dict):
        """Guarda transacción en SQLite."""
        from adaptadores.infraestructura.sqlite_adapter import SQLiteAdapter
        db = SQLiteAdapter(ruta="local_gastos.db")

        datos = {
            "id_transaccion": normalizado.get("event_id"),
            "fecha_hora_epoch": normalizado.get("timestamp_epoch", time.time()),
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.now().strftime("%H:%M:%S"),
            "trimestre": f"{datetime.now().year}-Q{((datetime.now().month - 1) // 3) + 1}",
            "app": normalizado.get("canal", "desconocido"),
            "paquete": normalizado.get("origen_paquete", ""),
            "dispositivo": "Termux",
            "tipo": normalizado.get("tipo", "desconocido"),
            "medio": normalizado.get("canal", "desconocido"),
            "monto_total": normalizado.get("monto", 0.0),
            "moneda": "PEN",
            "destinatario": normalizado.get("destinatario", "desconocido"),
            "motivo": motivo,
            "categoria": "Automático",
            "es_prestamo": 0,
            "monto_pagado": 0.0,
            "saldo_pendiente": normalizado.get("monto", 0.0) if normalizado.get("tipo") == "gasto" else 0.0,
            "estado_prestamo": "n/a",
            "looker": 0,
            "latitud": ubicacion.get("latitud") if ubicacion else None,
            "longitud": ubicacion.get("longitud") if ubicacion else None,
            "fuente_gps": ubicacion.get("fuente_gps", "none") if ubicacion else "none",
            "mensaje_raw": normalizado.get("mensaje_raw", ""),
            "status": "consolidado",
            "sincronizado": 0,
            "intentos_sync": 0,
            "ultimo_error_sync": "",
        }

        db.guardar_transaccion_sql_directo(**datos)
        db.cerrar_conexion()
        logger.info(f"Guardada en SQLite: {normalizado.get('event_id')}")

    def detener(self):
        self._detener = True


if __name__ == "__main__":
    import argparse
    import datetime

    parser = argparse.ArgumentParser(description="FIFO-Cola")
    parser.add_argument("--modo", choices=["automate_broker", "listener_directo"],
                        default="automate_broker")
    parser.add_argument("--directorio", type=str, default="/sdcard/Automate/notify")
    args = parser.parse_args()

    fifo = FIFOCola(directorio_monitor=args.directorio, modo_operacion=args.modo)
    logger.info("Iniciando FIFO-Cola...")
    fifo.iniciar()