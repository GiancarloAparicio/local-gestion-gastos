"""Capa de infraestructura multiplataforma (Termux / Linux).

Expone una fábrica ``obtener_proveedor(tipo)`` que devuelve la implementación
adecuada para el entorno actual, todas con el mismo contrato JSON.
"""

from . import config

from .input_provider import InputProvider
from .termux_input import TermuxInputProvider
from .linux_input import LinuxInputProvider

from .gps_provider import GPSProvider, TermuxGPSProvider, LinuxGPSProvider

from .database_provider import (
    SQLiteDatabaseProvider,
    TermuxDatabaseProvider,
    LinuxDatabaseProvider,
)

from .notification_provider import (
    NotificationProvider,
    TermuxNotificationProvider,
    LinuxNotificationProvider,
)


def obtener_proveedor(tipo: str):
    """Devuelve el proveedor por tipo: 'input', 'gps', 'database', 'notification'."""
    if tipo == "input":
        return TermuxInputProvider() if config.es_termux() else LinuxInputProvider()
    if tipo == "gps":
        return TermuxGPSProvider() if config.es_termux() else LinuxGPSProvider()
    if tipo == "database":
        # SQLite es idéntico en ambos entornos; la ruta la resuelve config.py
        return TermuxDatabaseProvider() if config.es_termux() else LinuxDatabaseProvider()
    if tipo == "notification":
        return TermuxNotificationProvider() if config.es_termux() else LinuxNotificationProvider()
    raise ValueError(f"Tipo de proveedor desconocido: {tipo}")


__all__ = [
    "config",
    "obtener_proveedor",
    "InputProvider",
    "TermuxInputProvider",
    "LinuxInputProvider",
    "GPSProvider",
    "TermuxGPSProvider",
    "LinuxGPSProvider",
    "SQLiteDatabaseProvider",
    "TermuxDatabaseProvider",
    "LinuxDatabaseProvider",
    "NotificationProvider",
    "TermuxNotificationProvider",
    "LinuxNotificationProvider",
]
