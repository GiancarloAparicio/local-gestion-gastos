"""Proveedor de base de datos SQLite (Termux y Linux).

SQLite es multiplataforma, por lo que la misma implementación sirve para ambos
entornos. La única diferencia real es la ruta del archivo, que se obtiene desde
config.yaml (``bd.ruta_sqlite``) mediante ``infraestructura.config``.

Todas las operaciones retornan el sobre JSON estándar:
    {"code": 0|-1, "data": {...}, "raw": "...", "valid": bool, "error": str|None}
"""

import json
import os
import time
import uuid
import sqlite3
from datetime import datetime

from infraestructura import config


# Columnas de la tabla transacciones en el orden usado para INSERT.
# Debe coincidir exactamente con el esquema creado en ``_crear_tablas``.
COLUMNAS_TRANSACCION = [
    "id_transaccion",
    "fecha_hora_epoch",
    "fecha_iso",
    "fecha",
    "hora",
    "trimestre",
    "app",
    "paquete",
    "dispositivo",
    "tipo",
    "medio",
    "monto_total",
    "moneda",
    "destinatario",
    "motivo",
    "categoria",
    "es_prestamo",
    "monto_pagado",
    "saldo_pendiente",
    "estado_prestamo",
    "looker",
    "latitud",
    "longitud",
    "fuente_gps",
    "mensaje_raw",
    "status",
    "sincronizado",
    "intentos_sync",
    "ultimo_error_sync",
]


def _sobre(code, data=None, raw="", error=None):
    """Construye el sobre JSON estándar."""
    return {
        "code": code,
        "data": data if data is not None else {},
        "raw": raw,
        "valid": code == 0,
        "error": error,
    }


class SQLiteDatabaseProvider:
    """Implementación concreta de persistencia sobre SQLite.

    Es única y compartida por Termux y Linux; la ruta se resuelve desde config.
    """

    def __init__(self, ruta_db: str = None):
        # Permite inyectar una ruta explícita (tests); si no, usa config.yaml.
        self._ruta_db = ruta_db or config.ruta_db()

    # --- utilidades internas -------------------------------------------------
    def _conectar(self):
        """Abre una conexión nueva a la base de datos configurada."""
        conexion = sqlite3.connect(self._ruta_db)
        conexion.row_factory = sqlite3.Row
        return conexion

    def _crear_tablas(self, cursor):
        """Crea las tres tablas del sistema si no existen."""
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_transaccion TEXT UNIQUE,
                fecha_hora_epoch REAL,
                fecha_iso TEXT,
                fecha TEXT,
                hora TEXT,
                trimestre TEXT,
                app TEXT,
                paquete TEXT,
                dispositivo TEXT,
                tipo TEXT,
                medio TEXT,
                monto_total REAL,
                moneda TEXT,
                destinatario TEXT,
                motivo TEXT,
                categoria TEXT,
                es_prestamo INTEGER,
                monto_pagado REAL,
                saldo_pendiente REAL,
                estado_prestamo TEXT,
                looker INTEGER,
                latitud REAL,
                longitud REAL,
                fuente_gps TEXT,
                mensaje_raw TEXT,
                status TEXT,
                sincronizado INTEGER,
                intentos_sync INTEGER,
                ultimo_error_sync TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notificaciones_crudas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recibido_en REAL,
                paquete TEXT,
                app TEXT,
                dispositivo TEXT,
                titulo TEXT,
                cuerpo TEXT,
                id_transaccion_vinculada TEXT,
                resultado_proceso TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS abonos_prestamo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_transaccion_prestamo TEXT,
                id_transaccion_ingreso TEXT,
                fecha_abono TEXT,
                monto_abono REAL,
                saldo_restante REAL,
                nota TEXT
            )
            """
        )
        # Migración ligera: bases antiguas pueden no tener 'fecha_iso'.
        columnas = {fila[1] for fila in cursor.execute("PRAGMA table_info(transacciones)")}
        if "fecha_iso" not in columnas:
            cursor.execute("ALTER TABLE transacciones ADD COLUMN fecha_iso TEXT")

    # --- API pública ---------------------------------------------------------
    def inicializar(self, ruta_db: str = None) -> dict:
        """Crea la base de datos y sus tablas si no existen."""
        if ruta_db:
            self._ruta_db = ruta_db
        try:
            conexion = self._conectar()
            self._crear_tablas(conexion.cursor())
            conexion.commit()
            conexion.close()
            return _sobre(
                0,
                {
                    "ruta": self._ruta_db,
                    "tablas": [
                        "transacciones",
                        "notificaciones_crudas",
                        "abonos_prestamo",
                    ],
                },
                raw=f"BD inicializada en {self._ruta_db}",
            )
        except Exception as e:  # pragma: no cover - defensivo
            return _sobre(-1, raw=str(e), error=str(e))

    def ejecutar_query(self, query: str, params: tuple = None) -> dict:
        """Ejecuta una sentencia SQL y retorna filas (SELECT) o afectadas."""
        conexion = None
        try:
            conexion = self._conectar()
            cursor = conexion.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if query.strip().upper().startswith("SELECT"):
                filas = [dict(fila) for fila in cursor.fetchall()]
                columnas = list(filas[0].keys()) if filas else []
                return _sobre(
                    0,
                    {"columnas": columnas, "filas": filas, "total": len(filas)},
                    raw=query[:120],
                )

            conexion.commit()
            afectadas = cursor.rowcount
            return _sobre(
                0,
                {"afectadas": afectadas},
                raw=query[:120],
            )
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))
        finally:
            if conexion is not None:
                conexion.close()

    def _normalizar_datos(self, datos: dict) -> dict:
        """Completa valores por defecto y deriva fecha/hora/trimestre."""
        # Acepta el timestamp de la notificación (epoch) además de fecha_hora_epoch.
        epoch = datos.get("fecha_hora_epoch", datos.get("timestamp_epoch"))
        if epoch is None:
            epoch = time.time()
        try:
            epoch = float(epoch)
        except (TypeError, ValueError):
            epoch = time.time()

        dt = datetime.fromtimestamp(epoch)
        fecha_iso = datos.get("fecha_hora") or datos.get("fecha_iso") or dt.isoformat()
        fecha = datos.get("fecha") or dt.strftime("%Y-%m-%d")
        hora = datos.get("hora") or dt.strftime("%H:%M:%S")
        trimestre = datos.get("trimestre") or f"{dt.year}-Q{((dt.month - 1) // 3) + 1}"

        tipo = datos.get("tipo") or "gasto"
        monto = datos.get("monto_total")
        if monto is None:
            monto = datos.get("monto", 0.0)
        try:
            monto = float(monto)
        except (TypeError, ValueError):
            monto = 0.0

        return {
            "id_transaccion": datos.get("id_transaccion") or datos.get("event_id") or str(uuid.uuid4()),
            "fecha_hora_epoch": epoch,
            "fecha_iso": fecha_iso,
            "fecha": fecha,
            "hora": hora,
            "trimestre": trimestre,
            "app": datos.get("app") or datos.get("canal") or "manual",
            "paquete": datos.get("paquete") or datos.get("origen_paquete") or "manual.entry",
            "dispositivo": datos.get("dispositivo") or "CLI-Manual",
            "tipo": tipo,
            "medio": datos.get("medio") or datos.get("canal") or "Transferencia",
            "monto_total": monto,
            "moneda": datos.get("moneda") or "PEN",
            "destinatario": datos.get("destinatario") or "desconocido",
            "motivo": datos.get("motivo"),
            "categoria": datos.get("categoria") or "Manual",
            "es_prestamo": int(datos.get("es_prestamo") or 0),
            "monto_pagado": float(datos.get("monto_pagado") or 0.0),
            "saldo_pendiente": float(
                datos.get("saldo_pendiente", monto if tipo == "gasto" else 0.0) or 0.0
            ),
            "estado_prestamo": datos.get("estado_prestamo") or "n/a",
            "looker": int(datos.get("looker") or 0),
            "latitud": datos.get("latitud"),
            "longitud": datos.get("longitud"),
            "fuente_gps": datos.get("fuente_gps") or "none",
            "mensaje_raw": datos.get("mensaje_raw") or "",
            "status": datos.get("status") or "consolidado",
            "sincronizado": int(datos.get("sincronizado") or 0),
            "intentos_sync": int(datos.get("intentos_sync") or 0),
            "ultimo_error_sync": datos.get("ultimo_error_sync") or "",
        }

    def insertar_transaccion(self, datos: dict) -> dict:
        """Inserta una transacción generando/validando su event_id (UUID)."""
        conexion = None
        try:
            normalizado = self._normalizar_datos(datos)
            columnas = COLUMNAS_TRANSACCION
            placeholders = ", ".join(["?"] * len(columnas))
            valores = tuple(normalizado[col] for col in columnas)

            conexion = self._conectar()
            cursor = conexion.cursor()
            self._crear_tablas(cursor)
            cursor.execute(
                f"INSERT INTO transacciones ({', '.join(columnas)}) VALUES ({placeholders})",
                valores,
            )
            conexion.commit()

            return _sobre(
                0,
                {
                    "event_id": normalizado["id_transaccion"],
                    "filas_afectadas": 1,
                },
                raw=f"Transacción insertada: {normalizado['id_transaccion']}",
            )
        except sqlite3.IntegrityError as e:
            # event_id duplicado: se considera ya registrada (idempotencia)
            return _sobre(
                -1,
                raw=str(e),
                error=f"event_id duplicado: {e}",
            )
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))
        finally:
            if conexion is not None:
                conexion.close()

    def listar_transacciones(self, limite: int = 10, sincronizado: int = None) -> dict:
        """Lista las últimas transacciones (opcionalmente por estado sync)."""
        try:
            if sincronizado is None:
                query = (
                    "SELECT id_transaccion, fecha, hora, tipo, monto_total, "
                    "destinatario, motivo, categoria, fuente_gps, sincronizado "
                    "FROM transacciones ORDER BY fecha_hora_epoch DESC LIMIT ?"
                )
                params = (int(limite),)
            else:
                query = (
                    "SELECT id_transaccion, fecha, hora, tipo, monto_total, "
                    "destinatario, motivo, categoria, fuente_gps, sincronizado "
                    "FROM transacciones WHERE sincronizado = ? "
                    "ORDER BY fecha_hora_epoch DESC LIMIT ?"
                )
                params = (int(sincronizado), int(limite))
            return self.ejecutar_query(query, params)
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))

    def actualizar_sincronizacion(self, event_id: str, status: int) -> dict:
        """Actualiza el estado de sincronización de una transacción."""
        try:
            conexion = self._conectar()
            cursor = conexion.cursor()
            cursor.execute(
                "UPDATE transacciones SET sincronizado = ?, ultimo_error_sync = '' "
                "WHERE id_transaccion = ?",
                (int(status), event_id),
            )
            conexion.commit()
            afectadas = cursor.rowcount
            conexion.close()
            return _sobre(0, {"afectadas": afectadas}, raw="sync actualizado")
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))

    def marcar_pendientes_sincronizadas(self) -> dict:
        """Marca como sincronizadas todas las transacciones pendientes."""
        try:
            conexion = self._conectar()
            cursor = conexion.cursor()
            cursor.execute(
                "UPDATE transacciones SET sincronizado = 1 WHERE sincronizado = 0"
            )
            conexion.commit()
            afectadas = cursor.rowcount
            conexion.close()
            return _sobre(0, {"afectadas": afectadas}, raw="pendientes sincronizadas")
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))

    def insertar_notificacion_cruda(self, datos_crudos: dict) -> dict:
        """Guarda la notificación tal cual llegó (log/auditoría).

        Retorna el ``id`` de la fila insertada para poder actualizarla luego
        con el event_id de la transacción y el resultado del proceso.
        """
        conexion = None
        try:
            paquete = (
                datos_crudos.get("packageName")
                or datos_crudos.get("package")
                or datos_crudos.get("paquete")
                or ""
            )
            app = datos_crudos.get("app") or datos_crudos.get("title") or paquete
            dispositivo = datos_crudos.get("device") or datos_crudos.get("dispositivo") or ""
            titulo = datos_crudos.get("title") or datos_crudos.get("titulo") or ""
            cuerpo = json.dumps(datos_crudos, ensure_ascii=False)

            conexion = self._conectar()
            cursor = conexion.cursor()
            self._crear_tablas(cursor)
            cursor.execute(
                "INSERT INTO notificaciones_crudas "
                "(recibido_en, paquete, app, dispositivo, titulo, cuerpo, "
                " id_transaccion_vinculada, resultado_proceso) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), paquete, app, dispositivo, titulo, cuerpo, None, "recibida"),
            )
            conexion.commit()
            nuevo_id = cursor.lastrowid
            return _sobre(0, {"id": nuevo_id}, raw="notificación cruda registrada")
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))
        finally:
            if conexion is not None:
                conexion.close()

    def actualizar_notificacion_cruda(
        self, crudo_id: int, event_id: str = None, resultado: str = None
    ) -> dict:
        """Actualiza el resultado y el event_id vinculado de una notificación cruda."""
        conexion = None
        try:
            conexion = self._conectar()
            cursor = conexion.cursor()
            cursor.execute(
                "UPDATE notificaciones_crudas "
                "SET id_transaccion_vinculada = COALESCE(?, id_transaccion_vinculada), "
                "    resultado_proceso = COALESCE(?, resultado_proceso) "
                "WHERE id = ?",
                (event_id, resultado, crudo_id),
            )
            conexion.commit()
            return _sobre(0, {"afectadas": cursor.rowcount})
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))
        finally:
            if conexion is not None:
                conexion.close()

    def insertar_abono(
        self,
        id_transaccion_prestamo: str,
        monto_abono: float,
        id_transaccion_ingreso: str = None,
        saldo_restante: float = None,
        nota: str = "",
    ) -> dict:
        """Registra un abono (pago) asociado a una transacción de préstamo.

        ``id_transaccion_prestamo`` referencia la transacción donde se prestó o
        se recibió dinero; ``id_transaccion_ingreso`` referencia el movimiento
        que salda parte de la deuda.
        """
        conexion = None
        try:
            conexion = self._conectar()
            cursor = conexion.cursor()
            self._crear_tablas(cursor)
            cursor.execute(
                "INSERT INTO abonos_prestamo "
                "(id_transaccion_prestamo, id_transaccion_ingreso, fecha_abono, "
                " monto_abono, saldo_restante, nota) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    id_transaccion_prestamo,
                    id_transaccion_ingreso,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    float(monto_abono),
                    saldo_restante,
                    nota,
                ),
            )
            conexion.commit()
            return _sobre(0, {"id": cursor.lastrowid}, raw="abono registrado")
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))
        finally:
            if conexion is not None:
                conexion.close()

    def obtener_ultima_ubicacion(self) -> dict:
        """Retorna la última ubicación válida registrada o None en ``data``."""
        try:
            conexion = self._conectar()
            cursor = conexion.cursor()
            cursor.execute(
                "SELECT latitud, longitud, fuente_gps FROM transacciones "
                "WHERE latitud IS NOT NULL AND longitud IS NOT NULL "
                "ORDER BY fecha_hora_epoch DESC LIMIT 1"
            )
            fila = cursor.fetchone()
            conexion.close()
            if fila:
                return _sobre(
                    0,
                    {
                        "latitud": fila["latitud"],
                        "longitud": fila["longitud"],
                        "fuente_gps": fila["fuente_gps"],
                    },
                    raw="última ubicación de la BD",
                )
            return _sobre(-1, raw="sin ubicaciones", error="sin ubicaciones")
        except Exception as e:
            return _sobre(-1, raw=str(e), error=str(e))


# Alias retrocompatibles: SQLite se comporta igual en ambos entornos.
class TermuxDatabaseProvider(SQLiteDatabaseProvider):
    """Alias para Termux (misma implementación SQLite)."""


class LinuxDatabaseProvider(SQLiteDatabaseProvider):
    """Alias para Linux (misma implementación SQLite)."""


class DatabaseFactory:
    """Fábrica que retorna el proveedor adecuado según el entorno."""

    @staticmethod
    def detectar_entorno() -> str:
        return config.entorno()

    @staticmethod
    def crear_proveedor() -> SQLiteDatabaseProvider:
        if config.es_termux():
            return TermuxDatabaseProvider()
        return LinuxDatabaseProvider()
