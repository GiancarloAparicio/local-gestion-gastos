"""Cola FIFO de procesamiento de notificaciones.

Soporta dos modos:
- ``automate_broker``: lee archivos JSON dejados por Automate en un directorio.
- ``listener_directo``: captura notificaciones nativas (solo Termux).

Enruta cada notificación al adaptador de su banco, normaliza, evita duplicados,
obtiene GPS y persiste usando la capa de persistencia multiplataforma
(``infraestructura.database_provider``).
"""

import hashlib
import json
import os
import time
from datetime import datetime

from infraestructura import config, obtener_proveedor
from modulios.consolidador import Consolidador
from modulios.logger import setup_logger

# Logger con salida a consola y a archivo (config.yaml → logging).
logger = setup_logger("FIFOCola")

# Valores "centinela" que significan dato no disponible (se deben preguntar).
MOTIVO_FALTANTE = {"", None, "sin motivo especificado"}
DEST_FALTANTE = {"", None, "desconocido", "por definir"}

# Mapeo por defecto paquete -> nombre de módulo del adaptador
MAPA_ADAPTADORES_DEFECTO = {
    "pe.com.interbank.mobilebanking": "ibk",
    "com.bcp.innovacxion.yapeapp": "yape",
    "com.google.android.apps.walletnfcrel": "nfc",
    "pe.com.compartamos.bancamovil": "compartamos",
    "manual.entry": "manual",
    # BBVA usa paquetes variables (com.bbva.*): se detecta por subcadena.
    "bbva": "bbva",
}


class FIFOCola:
    """Gestiona la cola FIFO de procesamiento de notificaciones."""

    def __init__(self, archivo_notificacion: str = None, modo_operacion: str = None):
        self.modo_operacion = modo_operacion or config.modo_operacion()
        self._detener = False
        self._procesados = set()
        # Único archivo que Automate reescribe en cada notificación.
        self.archivo_unico = archivo_notificacion or config.archivo_notificacion()
        self.directorio_monitor = os.path.dirname(self.archivo_unico) or config.RAIZ
        self.consolidador = Consolidador(ventana_minutos=config.ventana_consolidacion_minutos())
        # Combinar configuración + defaults
        self.mapa_adaptadores = dict(MAPA_ADAPTADORES_DEFECTO)
        for paquete, corto in config.mapeo_adaptadores().items():
            self.mapa_adaptadores[paquete] = str(corto)
        # Huella del último contenido procesado (persistida entre reinicios).
        self._ultima_clave = self._cargar_estado()

    # --- estado de idempotencia ---------------------------------------------
    def _ruta_estado(self) -> str:
        return os.path.join(config.RAIZ, ".broker_state.json")

    def _cargar_estado(self):
        """Carga la huella del último contenido procesado, si corresponde."""
        try:
            with open(self._ruta_estado(), "r", encoding="utf-8") as f:
                datos = json.load(f)
            if datos.get("archivo") == self.archivo_unico and datos.get("clave"):
                return tuple(datos["clave"])
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return None

    def _guardar_estado(self, clave: tuple) -> None:
        """Persiste la huella para evitar reprocesar el mismo contenido."""
        try:
            with open(self._ruta_estado(), "w", encoding="utf-8") as f:
                json.dump(
                    {"archivo": self.archivo_unico, "clave": list(clave)},
                    f,
                )
        except OSError:
            pass

    # --- utilidades ----------------------------------------------------------
    def _preparar_directorio(self) -> bool:
        """Prepara la fuente de entrada (archivo único o directorio).

        Si la ruta de config.yaml no es escribible (p. ej. ruta de Android en
        Linux), se usa un directorio local ``./noti_inbox`` como respaldo.
        """
        if self.archivo_unico:
            padre = os.path.dirname(self.archivo_unico) or config.RAIZ
            try:
                os.makedirs(padre, exist_ok=True)
                return True
            except (PermissionError, OSError):
                local = os.path.join(config.RAIZ, "noti_inbox")
                try:
                    os.makedirs(local, exist_ok=True)
                except OSError:
                    return False
                self.archivo_unico = os.path.join(local, "noti.json")
                self.directorio_monitor = local
                return True

        for candidato in (self.directorio_monitor, os.path.join(config.RAIZ, "noti_inbox")):
            try:
                os.makedirs(candidato, exist_ok=True)
                self.directorio_monitor = candidato
                return True
            except (PermissionError, OSError):
                continue
        logger.error(f"No se pudo preparar directorio de monitoreo: {self.directorio_monitor}")
        return False

    def _importar_adaptador(self, nombre: str):
        """Importa la clase de adaptador a partir de su nombre corto."""
        if not nombre:
            return None
        corto = str(nombre).lower().replace("adapter", "").strip()
        try:
            if corto == "ibk":
                from adaptadores.ibk import IBKAdapter
                return IBKAdapter()
            if corto == "yape":
                from adaptadores.yape import YapeAdapter
                return YapeAdapter()
            if corto == "nfc":
                from adaptadores.nfc import NFCAdapter
                return NFCAdapter()
            if corto == "compartamos":
                from adaptadores.compartamos import CompartamosAdapter
                return CompartamosAdapter()
            if corto == "manual":
                from adaptadores.manual import ManualAdapter
                return ManualAdapter()
            if corto == "bbva":
                from adaptadores.bbva import BBVAAdapter
                return BBVAAdapter()
        except ImportError as e:
            logger.warning(f"No se pudo importar adaptador '{nombre}': {e}")
        return None

    def _resolver_adaptador(self, paquete: str):
        """Determina el adaptador adecuado para un paquete de notificación."""
        for clave, corto in self.mapa_adaptadores.items():
            if clave in paquete:
                return self._importar_adaptador(corto)
        return None

    @staticmethod
    def _extraer_paquete(datos: dict) -> str:
        return (
            datos.get("packageName")
            or datos.get("package")
            or datos.get("paquete")
            or ""
        )

    # --- procesamiento -------------------------------------------------------
    def _registrar_crudo(self, datos: dict):
        """Guarda la notificación tal cual en ``notificaciones_crudas``."""
        db = obtener_proveedor("database")
        db.inicializar()
        res = db.insertar_notificacion_cruda(datos)
        if res.get("code") == 0:
            return res["data"].get("id")
        logger.error("No se pudo registrar notificación cruda: %s", res.get("error"))
        return None

    def _marcar_crudo(self, crudo_id, event_id=None, resultado=None):
        """Actualiza el resultado/event_id de la notificación cruda."""
        if crudo_id is None:
            return
        db = obtener_proveedor("database")
        db.actualizar_notificacion_cruda(crudo_id, event_id, resultado)

    def _preguntar_faltantes(self, normalizado: dict) -> dict:
        """Pide al usuario los datos faltantes.

        Termux → ``termux-dialog`` (via proveedor input).
        Linux  → ``input()`` de Python (via proveedor input).
        """
        input_prov = obtener_proveedor("input")

        # Monto
        try:
            monto = float(normalizado.get("monto") or 0)
        except (TypeError, ValueError):
            monto = 0.0
        if monto <= 0:
            r = input_prov.solicitar_numero(
                "Monto no detectado. ¿Cuál fue el monto?", min_val=0.01
            )
            if r.get("code") == 0:
                normalizado["monto"] = float(r["text"])
                logger.info("Monto ingresado por usuario: %s", normalizado["monto"])
            else:
                logger.warning("Monto no proporcionado (%s)", r.get("error"))

        # Tipo
        tipo = str(normalizado.get("tipo") or "").lower()
        if tipo not in ("gasto", "ingreso"):
            r = input_prov.solicitar_texto(
                "Tipo no detectado. ¿Es 'gasto' o 'ingreso'?"
            )
            val = (r.get("text") or "").strip().lower() if r.get("code") == 0 else ""
            if val in ("gasto", "ingreso"):
                normalizado["tipo"] = val
                logger.info("Tipo ingresado por usuario: %s", val)
            else:
                normalizado["tipo"] = "indeterminado"

        # Destinatario
        dest = normalizado.get("destinatario")
        if dest is None or str(dest).strip().lower() in DEST_FALTANTE:
            r = input_prov.solicitar_texto(
                "Destinatario no detectado. ¿Persona o comercio?"
            )
            if r.get("code") == 0 and (r.get("text") or "").strip():
                normalizado["destinatario"] = r["text"].strip()
                logger.info("Destinatario ingresado: %s", normalizado["destinatario"])

        # Motivo
        motivo = normalizado.get("motivo")
        if motivo is None or str(motivo).strip().lower() in MOTIVO_FALTANTE:
            r = input_prov.solicitar_texto("¿Cuál fue el motivo del movimiento?")
            if r.get("code") == 0 and (r.get("text") or "").strip():
                normalizado["motivo"] = r["text"].strip()
                logger.info("Motivo ingresado: %s", normalizado["motivo"])

        return normalizado

    @staticmethod
    def _datos_completos(n: dict) -> bool:
        """Valida que la transacción cumpla TODAS las reglas para guardarse."""
        try:
            monto = float(n.get("monto") or 0)
        except (TypeError, ValueError):
            monto = 0.0
        tipo = str(n.get("tipo") or "").lower()
        dest = str(n.get("destinatario") or "").strip().lower()
        motivo = str(n.get("motivo") or "").strip().lower()
        return (
            monto > 0
            and tipo in ("gasto", "ingreso")
            and dest not in DEST_FALTANTE
            and motivo not in MOTIVO_FALTANTE
        )

    def procesar_notificacion(self, datos: dict, origen: str = "broker") -> dict:
        """Procesa una notificación.

        Retorna un dict con ``ok_para_borrar`` (si puede eliminarse el archivo),
        ``event_id`` y ``estado``.
        """
        resultado = {"ok_para_borrar": False, "event_id": None, "estado": "desconocido"}

        # 0. Registrar SIEMPRE el crudo (log tal cual) en notificaciones_crudas.
        crudo_id = self._registrar_crudo(datos)
        if crudo_id is None:
            resultado["estado"] = "error_crudo"
            return resultado

        paquete = self._extraer_paquete(datos)
        if not paquete:
            logger.warning("Notificación sin paquete; se ignora")
            self._marcar_crudo(crudo_id, None, "ignorada_sin_paquete")
            resultado.update(ok_para_borrar=True, estado="ignorada_sin_paquete")
            return resultado

        adaptador = self._resolver_adaptador(paquete)
        if adaptador is None:
            logger.warning("Paquete no mapeado: %s", paquete)
            self._marcar_crudo(crudo_id, None, "ignorada_paquete_no_mapeado")
            resultado.update(ok_para_borrar=True, estado="ignorada_paquete_no_mapeado")
            return resultado

        logger.info("[%s] Adaptador=%s paquete=%s", origen, type(adaptador).__name__, paquete)
        try:
            normalizado = adaptador.normalizar_notificacion(datos)
        except Exception as e:
            logger.error("Error normalizando: %s", e, exc_info=True)
            self._marcar_crudo(crudo_id, None, "error_normalizacion")
            resultado.update(ok_para_borrar=False, estado="error_normalizacion")
            return resultado

        # Completar datos faltantes preguntando al usuario (Termux/Linux).
        normalizado = self._preguntar_faltantes(normalizado)
        logger.info(
            "Normalizado: monto=%s tipo=%s dest=%s motivo=%s",
            normalizado.get("monto"),
            normalizado.get("tipo"),
            normalizado.get("destinatario"),
            normalizado.get("motivo"),
        )

        # Duplicados: reglas del adaptador.
        if normalizado.get("es_duplicado"):
            logger.info("Duplicado según adaptador; se omite")
            self._marcar_crudo(crudo_id, None, "duplicado")
            resultado.update(ok_para_borrar=True, estado="duplicado")
            return resultado

        # Solo se guarda en transacciones si cumple TODAS las reglas.
        if not self._datos_completos(normalizado):
            logger.warning("Datos incompletos; NO se guarda en transacciones")
            self._marcar_crudo(crudo_id, None, "incompleta")
            resultado.update(ok_para_borrar=True, estado="incompleta")
            return resultado

        # GPS (opcional; si falla se guarda con fuente_gps=none).
        ubicacion = obtener_proveedor("gps").obtener_ubicacion()
        if ubicacion.get("code") == 0:
            normalizado["latitud"] = ubicacion["data"].get("lat")
            normalizado["longitud"] = ubicacion["data"].get("lng")
            normalizado["fuente_gps"] = ubicacion["data"].get("source", "none")
        else:
            normalizado["latitud"] = None
            normalizado["longitud"] = None
            normalizado["fuente_gps"] = "none"

        db = obtener_proveedor("database")
        db.inicializar()
        res = db.insertar_transaccion(normalizado)
        if res.get("code") == 0:
            event_id = res["data"]["event_id"]
            logger.info("Transacción guardada: %s", event_id)
            self._marcar_crudo(crudo_id, event_id, "procesada")
            resultado.update(ok_para_borrar=True, event_id=event_id, estado="procesada")
        else:
            logger.error("No se pudo guardar transacción: %s", res.get("error"))
            self._marcar_crudo(crudo_id, None, "error_bd")
            resultado.update(ok_para_borrar=False, estado="error_bd")
        return resultado

    def _procesar_payload(self, datos):
        """Procesa un objeto o lista. Retorna (insertados, todos_borrables)."""
        items = datos if isinstance(datos, list) else [datos]
        items = [i for i in items if isinstance(i, dict)]
        insertados = 0
        todos_borrables = len(items) > 0
        for item in items:
            r = self.procesar_notificacion(item, "automate_file")
            if r.get("estado") == "procesada":
                insertados += 1
            if not r.get("ok_para_borrar"):
                todos_borrables = False
        return insertados, todos_borrables

    def _procesar_archivo_unico(self) -> int:
        """Procesa el ÚNICO archivo de notificación que Automate reescribe.

        Reglas:
        - Detecta cambios por (mtime_ns, tamaño, SHA-1).
        - JSON incompleto (escritura en curso): no se marca, se reintenta.
        - Al terminar el procesamiento se ELIMINA el archivo JSON.
        - Si hubo un error grave (crudo/BD), se conserva para reintento.
        """
        ruta = self.archivo_unico
        if not ruta or not os.path.isfile(ruta):
            return 0

        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
            st = os.stat(ruta)
        except OSError as e:
            logger.debug("No se pudo leer %s: %s", ruta, e)
            return 0

        if not contenido.strip():
            return 0

        huella = hashlib.sha1(contenido.encode("utf-8")).hexdigest()
        clave = (st.st_mtime_ns, st.st_size, huella)
        if clave in self._procesados or clave == self._ultima_clave:
            return 0

        try:
            datos = json.loads(contenido)
        except json.JSONDecodeError as e:
            # Escritura parcial: reintentar en el próximo ciclo sin marcar.
            logger.warning("JSON incompleto en %s (%s); se reintentará", ruta, e)
            return 0

        insertados, todos_borrables = self._procesar_payload(datos)

        if todos_borrables:
            # Registrar huella y eliminar el archivo (Automate lo recreará).
            self._procesados.add(clave)
            self._ultima_clave = clave
            self._guardar_estado(clave)
            try:
                os.remove(ruta)
                logger.info("Archivo procesado y eliminado: %s", ruta)
            except OSError as e:
                logger.warning("No se pudo eliminar %s: %s", ruta, e)
        else:
            logger.warning("Se conserva el archivo para reintento: %s", ruta)

        return insertados

    def _procesar_automate_broker(self) -> int:
        """Modo broker: lee el archivo único de notificación."""
        return self._procesar_archivo_unico()

    def _procesar_listener_directo(self) -> int:
        """Captura una notificación nativa (solo Termux)."""
        if not config.es_termux():
            logger.warning("listener_directo solo está disponible en Termux")
            return 0
        proveedor = obtener_proveedor("notification")
        captura = proveedor.capturar_notificacion()
        if captura.get("code") != 0:
            return 0
        self.procesar_notificacion(captura["data"], "listener")
        return 1

    # --- ciclo de vida -------------------------------------------------------
    def procesar_una_vez(self) -> int:
        """Ejecuta un único ciclo de procesamiento y retorna cuántos procesó."""
        if self.modo_operacion == "automate_broker":
            return self._procesar_automate_broker()
        if self.modo_operacion == "listener_directo":
            return self._procesar_listener_directo()
        logger.warning(f"Modo desconocido: {self.modo_operacion}")
        return 0

    def iniciar(self, una_vez: bool = False):
        """Inicia el bucle de monitoreo (o un único ciclo si ``una_vez``)."""
        if self.modo_operacion == "listener_directo" and not config.es_termux():
            logger.error("El modo listener_directo requiere Termux (Android). Use --broker.")
            return

        if self.modo_operacion == "automate_broker":
            self._preparar_directorio()

        logger.info(f"🚀 FIFO-Cola modo={self.modo_operacion} dir={self.directorio_monitor}")

        if una_vez:
            total = self.procesar_una_vez()
            logger.info(f"Ciclo único completado: {total} notificaciones")
            return

        try:
            while not self._detener:
                self.procesar_una_vez()
                time.sleep(int(config.valor("automate_broker", "monitoreo_polling_segundos", default=5)))
        except KeyboardInterrupt:
            logger.info("⏹️  FIFO-Cola detenida por el usuario")
        finally:
            self._detener = True

    def detener(self):
        self._detener = True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FIFO-Cola")
    parser.add_argument("--modo", choices=["automate_broker", "listener_directo"],
                        default=config.modo_operacion())
    parser.add_argument("--archivo", default=None,
                        help="Ruta del archivo único de notificación (noti.json)")
    parser.add_argument("--una-vez", action="store_true")
    args = parser.parse_args()

    FIFOCola(archivo_notificacion=args.archivo, modo_operacion=args.modo).iniciar(
        una_vez=args.una_vez
    )
