"""Implementación concreta de DatabaseAdapter usando SQLite."""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List


class SQLiteAdapter:
    """Adaptador de base de datos SQLite para el sistema local-gestion-gastos."""

    def __init__(self, db_ruta: str = None, ruta: str = None):
        # 'ruta' se acepta como alias retrocompatible de 'db_ruta'.
        if db_ruta is None:
            db_ruta = ruta
        if db_ruta is None:
            try:
                from infraestructura import config
                db_ruta = config.ruta_db()
            except Exception:
                db_ruta = "local_gastos.db"
        self.db_ruta = db_ruta
        self._conexion = None
        self._inicializar_bd()

    def cerrar_conexion(self):
        """Cierra la conexión activa si existe."""
        if self._conexion is not None:
            try:
                self._conexion.close()
            finally:
                self._conexion = None

    def _obtener_conexion(self):
        """Obtiene o crea la conexión, asegurando que esté abierta."""
        if self._conexion is None:
            self._conexion = sqlite3.connect(self.db_ruta)
        return self._conexion

    def _inicializar_bd(self):
        """Crea las tablas si no existen. No cierra la conexión después."""
        conn = self._obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
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
        ''')
        cursor.execute('''
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
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS abonos_prestamo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_transaccion_prestamo TEXT,
                id_transaccion_ingreso TEXT,
                fecha_abono TEXT,
                monto_abono REAL,
                saldo_restante REAL,
                nota TEXT
            )
        ''')
        # No cerramos la conexión aquí; la mantenemos abierta para su uso posterior
        # self._conexion ya fue asignado en _obtener_conexion()

    def guardar_transaccion_sql_directo(self, **kwargs):
        conn = self._obtener_conexion()
        cursor = conn.cursor()
        columnas = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        valores = tuple(kwargs.values())
        cursor.execute(
            f"INSERT INTO transacciones ({columnas}) VALUES ({placeholders})",
            valores,
        )
        self._conexion.commit()

    def actualizar_sincronizacion(self, event_id, status):
        conn = self._obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE transacciones SET sincronizado = ?, ultimo_error_sync = '' WHERE id_transaccion = ?",
            (status, event_id),
        )
        self._conexion.commit()

    def verificar_duplicado_ventana(self, datos):
        conn = self._obtener_conexion()
        cursor = conn.cursor()
        tiempo_limite = 300
        epoch_limite = datetime.now().timestamp() - tiempo_limite
        cursor.execute(
            "SELECT COUNT(*) FROM transacciones WHERE tipo = ? AND ABS(monto_total - ?) < 0.10 * ? AND fecha_hora_epoch > ?",
            (datos.get("tipo"), datos.get("monto_total"), datos.get("monto_total", 1), epoch_limite),
        )
        count = cursor.fetchone()[0]
        return count > 0

    def obtener_ultima_ubicacion(self):
        conn = self._obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT latitud, longitud, fuente_gps FROM transacciones WHERE latitud IS NOT NULL AND longitud IS NOT NULL ORDER BY fecha_hora_epoch DESC LIMIT 1"
        )
        fila = cursor.fetchone()
        if fila:
            return {"latitud": fila[0], "longitud": fila[1], "fuente_gps": fila[2]}
        return None

    def listar_transacciones(self, limite=10, sincronizado=None):
        conn = self._obtener_conexion()
        cursor = conn.cursor()
        if sincronizado is not None:
            cursor.execute(
                "SELECT id_transaccion, fecha_hora_epoch, fecha, tipo, monto_total, destinatario, motivo, sincronizado FROM transacciones WHERE sincronizado = ? ORDER BY fecha_hora_epoch DESC LIMIT ?",
                (sincronizado, limite),
            )
        else:
            cursor.execute(
                "SELECT id_transaccion, fecha_hora_epoch, fecha, tipo, monto_total, destinatario, motivo FROM transacciones ORDER BY fecha_hora_epoch DESC LIMIT ?",
                (limite,),
            )
        columnas = [desc[0] for desc in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

    # Ya no tenemos método cerrar_conexion() público; Python hará cleanup al final
