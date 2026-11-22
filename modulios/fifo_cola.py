"""Módulo FIFO (First-In-First-Out) para el procesamiento de notificaciones."""

import os
import sys
import json
import time
import re
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

# Paquetes de bancos a monitorear (documentación ARCHITECTURE.md Section 13.1)
PAQUETES_BANCOS = [
    "pe.com.interbank.mobilebanking",
    "com.bcp.innovacxion.yapeapp",
    "com.google.android.apps.walletnfcrel",
    "com.android.shell",
    "pe.com.compartamos.bancamovil",
]

consolidador = Consolidador(ventana_minutos=5)


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
        self.mapa_adaptadores = {
            "pe.com.interbank.mobilebanking": "IBKAdapter",
            "com.bcp.innovacxion.yapeapp": "YapeAdapter",
        }

    def iniciar(self):
        logger.info("🚀 Iniciando FIFO-Cola en modo: %s", self.modo_operacion)
        logger.info("📁 Directorio: %s", self.directorio_monitor)
        logger.info("📦 Paquetes: %d", len(PAQUETES_BANCOS))

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
        while not self._detener:
            try:
                if self.modo_operacion == "automate_broker":
                    self._procesar_automate_broker()
                elif self.modo_operacion == "listener_directo":
                    self._capturar_listener_directo()
                else:
                    logger.warning("⚠️  Modo desconocido: %s", self.modo_operacion)
                    time.sleep(2)
            except Exception as e:
                logger.error("❌ Error en bucle principal: %s", e)
                time.sleep(2)

    def _procesar_automate_broker(self):
        try:
            archivos = []
            if os.path.exists(self.directorio_monitor):
                for nombre in os.listdir(self.directorio_monitor):
                    ruta = os.path.join(self.directorio_monitor, nombre)
                    if os.path.isfile(ruta):
                        tiempo = os.path.getmtime(ruta)
                        archivos.append((nombre, tiempo, ruta))

                archivos.sort(key=lambda x: x[1])
                logger.info("📦 Se encontraron %d archivos nuevos", len(archivos))

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
                        self._procesar_notificacion(datos, origen="automate_file")
                        time.sleep(0.5)
                        self._ultimo_marcador = time.time()
                    except Exception as e:
                        logger.error("❌ Error archivo %s: %s", nombre_archivo, e)
                        continue
            logger.info("🔄 Finalizado procesamiento broker Automate")
        except Exception as e:
            logger.error("❌ Error en procesamiento broker: %s", e)

    def _capturar_listener_directo(self):
        try:
            logger.info("🔔 Verificando notificaciones entrantes (listener)...")
            self._procesar_notificacion_prueba()
        except Exception as e:
            logger.error("❌ Error captura directa: %s", e)

    def _procesar_notificacion_prueba(self):
        logger.info("🔧 test: procesando notificación de ejemplo")

    def _procesar_notificacion(self, datos_notificacion: dict, origen: str):
        try:
            paquete = datos_notificacion.get("package") or \
                      datos_notificacion.get("packageName") or \
                      datos_notificacion.get("paquete", "")

            adaptador_nombre = self.mapa_adaptadores.get(paquete)
            if adaptador_nombre:
                logger.info("✅ Adaptador: %s", adaptador_nombre)
                normalizado = self._normalizar_datos(adaptador_nombre, datos_notificacion)
                logger.info("📊 monto: %s, tipo: %s, destinatario: %s",
                           normalizado.get("monto"), normalizado.get("tipo"),
                           normalizado.get("destinatario"))

                ya_existe = consolidador.debe_consolidar(
                    datetime.fromtimestamp(normalizado.get("timestamp_epoch", time.time())),
                    datetime.now() - consolidador.ventana_timedelta
                )
                if ya_existe:
                    logger.info("♻️  consolidada en registro existente")
                else:
                    logger.info("❓ solicitando motivo al usuario")
                    self._solicitar_motivo(normalizado)
                    ubicacion = self._obtener_ubicacion()
                    self._guardar_sqlite(normalizado, ubicacion)
                    logger.info("✅ guardada en SQLite")

            else:
                logger.info("📝 paquete no mapeado: %s", paquete)

            time.sleep(0.3)

        except Exception as e:
            logger.error("❌ error procesando notificación: %s", e)

    def _importar_adaptador(self, nombre: str):
        try:
            normalized = nombre.lower()
            if normalized == "ibk":
                from adaptadores.ibk import IBKAdapter
                return IBKAdapter()
            elif normalized == "yape":
                from adaptadores.yape import YapeAdapter
                return YapeAdapter()
            return None
        except ImportError:
            logger.warning("⚠️  no se pudo importar adaptador: %s", nombre)
            return None

    def _normalizar_datos(self, adaptador_nombre: str, datos: dict) -> dict:
        try:
            if adaptador_nombre == "IBKAdapter":
                from adaptadores.ibk import IBKAdapter
                adaptador = IBKAdapter()
            elif adaptador_nombre == "YapeAdapter":
                from adaptadores.yape import YapeAdapter
                adaptador = YapeAdapter()
            else:
                adaptador = None

            if adaptador and hasattr(adaptador, "normalizar_notificacion"):
                return adaptador.normalizar_notificacion(datos)
            return {
                "monto": 0.0, "tipo": "desconocido", "destinatario": "desconocido",
                "event_id": str(time.time()), "canal": "desconocido",
                "fecha_hora": datetime.now().isoformat(), "mensaje_raw": "",
                "motivo": None, "fuente": "por_definir",
                "origen_paquete": datos.get("package", ""),
                "titulo_visual": datos.get("title", ""), "timestamp_epoch": time.time()
            }
        except Exception as e:
            logger.error("❌ error normalizando: %s", e)
            return {"monto": 0.0, "tipo": "desconocido", "destinatario": "desconocido",
                   "event_id": str(time.time()), "canal": "desconocido",
                   "fecha_hora": datetime.now().isoformat(), "mensaje_raw": "",
                   "motivo": None, "fuente": "por_definir",
                   "origen_paquete": "", "titulo_visual": "",
                   "timestamp_epoch": time.time()}

    def _solicitar_motivo(self, normalizado: dict):
        logger.info("❓ solicitando motivo al usuario")

    def _obtener_ubicacion(self):
        import random
        escenario = random.choice(["live", "last_known", "none"])
        if escenario == "live":
            return {"latitud": -12.0458, "longitud": -77.0237, "fuente_gps": "live"}
        elif escenario == "last_known":
            return {"latitud": -11.9942, "longitud": -77.0628, "fuente_gps": "last_known"}
        return {"latitud": None, "longitud": None, "fuente_gps": "none"}

    def _guardar_sqlite(self, normalizado: dict, ubicacion: Optional[dict]):
        from adaptadores.infraestructura.sqlite_adapter import SQLiteAdapter
        db = SQLiteAdapter(ruta="local_gastos.db")
        db.guardar_transaccion_sql_directo(
            id_transaccion=normalizado.get("event_id"),
            fecha_hora_epoch=normalizado.get("timestamp_epoch", time.time()),
            fecha=datetime.now().strftime("%Y-%m-%d"),
            hora=datetime.now().strftime("%H:%M:%S"),
            trimestre=f"{datetime.now().year}-Q{((datetime.now().month - 1) // 3) + 1}",
            app=normalizado.get("canal", "desconocido"),
            paquete=normalizado.get("origen_paquete", ""),
            dispositivo="Termux",
            tipo=normalizado.get("tipo", "desconocido"),
            medio=normalizado.get("canal", "desconocido"),
            monto_total=normalizado.get("monto", 0.0),
            moneda="PEN",
            destinatario=normalizado.get("destinatario", "desconocido"),
            motivo="",
            categoria="Automático",
            es_prestamo=0,
            monto_pagado=0.0,
            saldo_pendiente=normalizado.get("monto", 0.0) if normalizado.get("tipo") == "gasto" else 0.0,
            estado_prestamo="n/a",
            looker=0,
            latitud=ubicacion.get("latitud") if ubicacion else None,
            longitud=ubicacion.get("longitud") if ubicacion else None,
            fuente_gps=ubicacion.get("fuente_gps", "none") if ubicacion else "none",
            mensaje_raw=normalizado.get("mensaje_raw", ""),
            status="consolidado",
            sincronizado=0,
            intentos_sync=0,
            ultimo_error_sync="",
        )
        db.cerrar_conexion()
        logger.info("💾 guardada en SQLite: %s", normalizado.get("event_id"))

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
    logger.info("🚀 Iniciando FIFO-Cola...")
    fifo.iniciar()