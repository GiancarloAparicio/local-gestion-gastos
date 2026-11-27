# infraestructura/__init__.py
# Paquete de proveedores abstractos para el sistema local-gestion-gastos
# Proporciona interfaces unificadas para entrada de datos, GPS, BD y notificaciones
# que funcionan indistintamente en Termux (Android) y Linux standard.

# Importaciones de los proveedores de entrada de datos
from .input_provider import InputProvider  # Clase base abstracta
from .termux_input import TermuxInputProvider  # Implementación Termux
from .linux_input import LinuxInputProvider  # Implementación Linux

# Importaciones de proveedores GPS
from .gps_provider import GPSProvider, TermuxGPSProvider, LinuxGPSProvider

# Importaciones de proveedores de BD
from .database_provider import DatabaseProvider, TermuxDatabaseProvider, LinuxDatabaseProvider

# Importaciones de proveedores de notificaciones
from .notification_provider import NotificationProvider, TermuxNotificationProvider, LinuxNotificationProvider


def obtener_proveedor(tipo: str) -> object:
    """Obtener proveedor por tipo: 'input', 'gps', 'database', 'notification'"""
    import os
    import sys
    
    # Detectar entorno basándose en variables de entorno de Termux
    termux_signs = ["ANDROID_DATA", "EXTERNAL_STORAGE", "com.termux", "TERMUX_VERSION"]
    es_termux = any(sign in os.environ for sign in termux_signs)
    
    if tipo == "input":
        if es_termux:
            return TermuxInputProvider()
        else:
            return LinuxInputProvider()
    
    elif tipo == "gps":
        if es_termux:
            return TermuxGPSProvider()
        else:
            return LinuxGPSProvider()
    
    elif tipo == "database":
        # SQLite es cross-platform, usar TermuxDatabaseProvider (tiene lógica completa)
        return TermuxDatabaseProvider()
    
    elif tipo == "notification":
        if es_termux:
            return TermuxNotificationProvider()
        else:
            return LinuxNotificationProvider()
    
    else:
        raise ValueError(f"Tipo de proveedor desconocido: {tipo}")


# Alias para compatibilidad
crear_input = obtener_proveedor
crear_gps = obtener_proveedor
crear_db = obtener_proveedor
crear_notif = obtener_proveedor