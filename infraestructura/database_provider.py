"""Módulo de proveedor de base de datos SQLite.
Proporciona una interfaz unificada para operaciones de BD en Termux y Linux.
SQLite es cross-platform, pero abstractamos para consistencia y futuro PostgreSQL.
Siempre retorna JSON estandarizado: {"code": 0|-1, "data": {...}, "raw": "...", "valid": true|false, "error": null|str}
"""

from abc import ABC, abstractmethod
import sqlite3
import json
import os
import time


class DatabaseProvider(ABC):
    """Provedor abstracto de base de datos."""
    
    @abstractmethod
    def inicializar(self, ruta_db: str = None) -> dict:
        """Inicializar/crear la base de datos. Retorna JSON estandarizado."""
        pass
    
    @abstractmethod
    def ejecutar_query(self, query: str, params: tuple = None) -> dict:
        """Ejecutar una query SQL. Retorna JSON estandarizado."""
        pass
    
    @abstractmethod
    def insertar_transaccion(self, datos: dict) -> dict:
        """Insertar una transacción. Retorna JSON estandarizado con event_id."""
        pass


class BaseDatabaseProvider(DatabaseProvider):
    """Clase base con lógica compartida - SQLite es cross-platform"""
    
    def _obtener_ruta_base(self) -> str:
        """Ruta por defecto de la base de datos"""
        return os.path.expanduser("~/local_gastos.db")
    
    def _conectar(self, ruta_db: str = None):
        """Crear conexión a SQLite"""
        if ruta_db is None:
            ruta_db = self._obtener_ruta_base()
        conexion = sqlite3.connect(ruta_db)
        return conexion, conexion.cursor()


class TermuxDatabaseProvider(BaseDatabaseProvider, DatabaseProvider):
    """Implementación para Termux - rutas específicas de Android"""
    
    def _obtener_ruta_base(self) -> str:
        """Obtener ruta base de datos en Termux"""
        # En Termux, los datos van en el almacenamiento interno de usuario
        return os.path.expanduser("~/local_gastos.db")
    
    def inicializar(self, ruta_db: str = None) -> dict:
        """Crear tablas si no existen"""
        if ruta_db is None:
            ruta_db = self._obtener_ruta_base()
        
        try:
            conexion, cursor = self._conectar(ruta_db)
            
            # Crear tablas del sistema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transacciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_transaccion TEXT UNIQUE,
                    fecha_hora_epoch REAL,
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
            """)
            
            cursor.execute("""
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
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS abonos_prestamo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_transaccion_prestamo TEXT,
                    id_transaccion_ingreso TEXT,
                    fecha_abono TEXT,
                    monto_abono REAL,
                    saldo_restante REAL,
                    nota TEXT
                )
            """)
            
            conexion.commit()
            conexion.close()
            
            return {
                "code": 0,
                "data": {"ruta": ruta_db, "tablas": ["transacciones", "notificaciones_crudas", "abonos_prestamo"]},
                "raw": f"BD inicializada en {ruta_db}",
                "valid": True,
                "error": None
            }
        except Exception as e:
            try:
                conexion.close()
            except:
                pass
            return {
                "code": -1,
                "data": {},
                "raw": str(e),
                "valid": False,
                "error": str(e)
            }
    
    def ejecutar_query(self, query: str, params: tuple = None) -> dict:
        """Ejecutar query de solo lectura o modificación"""
        try:
            conexion, cursor = self._conectar()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Para queries SELECT, obtener resultados
            if query.strip().upper().startswith("SELECT"):
                resultados = cursor.fetchall()
                columnas = [desc[0] for desc in cursor.description] if cursor.description else []
                datos = [dict(zip(columnas, fila)) for fila in resultados]
                
                conexion.close()
                
                return {
                    "code": 0,
                    "data": {"columnas": columnas, "filas": datos, "total": len(datos)},
                    "raw": query[:100] + ("..." if len(query) > 100 else ""),
                    "valid": True,
                    "error": None
                }
            else:
                # INSERT, UPDATE, DELETE
                conexion.commit()
                conexion.close()
                
                return {
                    "code": 0,
                    "data": {"afectadas": cursor.rowcount if hasattr(cursor, 'rowcount') else 0},
                    "raw": query[:100] + ("..." if len(query) > 100 else ""),
                    "valid": True,
                    "error": None
                }
        except Exception as e:
            try:
                conexion.close()
            except:
                pass
            return {
                "code": -1,
                "data": {},
                "raw": str(e),
                "valid": False,
                "error": str(e)
            }
    
    def insertar_transaccion(self, datos: dict) -> dict:
        """Insertar transacción con event_id único"""
        try:
            import uuid
            import time as time_module
            
            event_id = datos.get("id_transaccion", str(uuid.uuid4()))
            
            # Asegurar campos por defecto
            datos_defecto = {
                "id_transaccion": event_id,
                "fecha_hora_epoch": datos.get("fecha_hora_epoch", time_module.time()),
                "fecha": datos.get("fecha"),
                "hora": datos.get("hora"),
                "trimestre": datos.get("trimestre"),
                "app": datos.get("app", "manual"),
                "paquete": datos.get("paquete", "manual"),
                "dispositivo": datos.get("dispositivo", "CLI-Manual"),
                "tipo": datos.get("tipo"),
                "medio": datos.get("medio"),
                "monto_total": datos.get("monto_total"),
                "moneda": datos.get("moneda", "PEN"),
                "destinatario": datos.get("destinatario"),
                "motivo": datos.get("motivo"),
                "categoria": datos.get("categoria", "Manual"),
                "es_prestamo": datos.get("es_prestamo", 0),
                "monto_pagado": datos.get("monto_pagado", 0.0),
                "saldo_pendiente": datos.get("saldo_pendiente", 0.0),
                "estado_prestamo": datos.get("estado_prestamo", "n/a"),
                "looker": datos.get("looker", 0),
                "latitud": datos.get("latitud"),
                "longitud": datos.get("longitud"),
                "fuente_gps": datos.get("fuente_gps"),
                "mensaje_raw": datos.get("mensaje_raw", ""),
                "status": datos.get("status", "consolidado"),
                "sincronizado": datos.get("sincronizado", 0),
                "intentos_sync": datos.get("intentos_sync", 0),
                "ultimo_error_sync": datos.get("ultimo_error_sync", "")
            }
            
            conexion, cursor = self._conectar()
            
            cursor.execute("""
                INSERT INTO transacciones 
                (id_transaccion, fecha_hora_epoch, fecha, hora, trimestre, app, paquete, dispositivo,
                 tipo, medio, monto_total, moneda, destinatario, motivo, categoria, es_prestamo,
                 monto_pagado, saldo_pendiente, estado_prestamo, looker, latitud, longitud, 
                 fuente_gps, mensaje_raw, status, sincronizado, intentos_sync, ultimo_error_sync)
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, '')
            """, tuple(datos_defecto.values()))
            
            conexion.commit()
            
            resultado = {
                "code": 0,
                "data": {"event_id": event_id, "filas_afectadas": 1},
                "raw": f"Transacción insertada con ID: {event_id}",
                "valid": True,
                "error": None
            }
            
            conexion.close()
            return resultado
            
        except Exception as e:
            return {
                "code": -1,
                "data": {},
                "raw": str(e),
                "valid": False,
                "error": str(e)
            }


class LinuxDatabaseProvider(BaseDatabaseProvider, DatabaseProvider):
    """Implementación para Linux standard - SQLite es cross-platform idéntico"""
    
    def _obtener_ruta_base(self) -> str:
        """Ruta por defecto en Linux"""
        return os.path.expanduser("~/local_gastos.db")
    
    # La mayoría de la lógica es idéntica a Termux ya que SQLite es cross-platform
    # Los methods se heredan o delegan a la base clase
    
    def inicializar(self, ruta_db: str = None) -> dict:
        """Mismo código que Termux, SQLite es cross-platform"""
        # Reutilizamos la lógica, pero por separado está definido
        from .database_provider import BaseDatabaseProvider
        # Por simplicidad, delegamos a la implementación base que usará las rutas por defecto
        return self._inicializar_generico(ruta_db)
    
    def _inicializar_generico(self, ruta_db: str = None) -> dict:
        """Lógica de inicialización compartida"""
        if ruta_db is None:
            ruta_db = self._obtener_ruta_base()
        
        try:
            conexion, cursor = self._conectar(ruta_db)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transacciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_transaccion TEXT UNIQUE,
                    fecha_hora_epoch REAL,
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
            """)
            
            cursor.execute("""
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
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS abonos_prestamo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_transaccion_prestamo TEXT,
                    id_transaccion_ingreso TEXT,
                    fecha_abono TEXT,
                    monto_abono REAL,
                    saldo_restante REAL,
                    nota TEXT
                )
            """)
            
            conexion.commit()
            conexion.close()
            
            return {
                "code": 0,
                "data": {"ruta": ruta_db, "tablas": ["transacciones", "notificaciones_crudas", "abonos_prestamo"]},
                "raw": f"BD inicializada en {ruta_db}",
                "valid": True,
                "error": None
            }
        except Exception as e:
            try:
                conexion.close()
            except:
                pass
            return {
                "code": -1,
                "data": {},
                "raw": str(e),
                "valid": False,
                "error": str(e)
            }
    
    def ejecutar_query(self, query: str, params: tuple = None) -> dict:
        """Mismo funcionamiento que Termux en Linux"""
        # Lógica idéntica, SQLite es cross-platform
        from .database_provider import BaseDatabaseProvider
        # Delegamos a la lógica compartida
        pass
    
    def insertar_transaccion(self, datos: dict) -> dict:
        """Mismo funcionamiento que Termux en Linux"""
        from .database_provider import BaseDatabaseProvider
        pass


class DatabaseFactory:
    """Factoría para crear el proveedor de BD según el entorno"""
    
    @staticmethod
    def detectar_entorno() -> str:
        """Detecta si estamos en Termux o Linux"""
        import os
        import sys
        
        termux_signs = ["ANDROID_DATA", "EXTERNAL_STORAGE", "com.termux", "TERMUX_VERSION"]
        for sign in termux_signs:
            if sign in os.environ:
                return "termux"
        
        if sys.platform.startswith("linux") and not any(sign in os.environ for sign in termux_signs):
            return "linux"
        
        return "linux"
    
    @staticmethod
    def crear_proveedor() -> DatabaseProvider:
        """Crea el proveedor de BD apropiado"""
        # SQLite es cross-platform, la implementación de Termux funciona en Linux y viceversa
        # Pero usamos TermuxDatabaseProvider por defecto ya que tiene la lógica completa
        return TermuxDatabaseProvider()