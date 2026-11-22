"""Entidades de dominio - Lógica de negocio pura sin dependencias externas."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaccion:
    """Representa un movimiento financiero consolidado y limpio."""
    id_transaccion: str
    fecha_hora_epoch: float
    fecha: str  # YYYY-MM-DD
    hora: str  # HH:MM:SS
    trimestre: str  # Ej: 2026-Q4
    app: str  # Aplicación origen
    paquete: str  # Paquete Android
    dispositivo: str  # Nombre del dispositivo
    tipo: str  # "Ingreso" o "Gasto"
    medio: str  # "Cuenta", "Tarjeta", "NFC", "Transferencia", etc.
    monto_total: float  # Monto en PEN
    moneda: str  # "PEN"
    destinatario: str  # Persona o comercio
    motivo: str  # Descripción del movimiento (siempre tiene valor después de prompt)
    categoria: str  # Clasificación (Prestamos, Comestibles, Manual, etc.)
    es_prestamo: int  # 1 = sí, 0 = no
    monto_pagado: float  # Para préstamos: cuotas pagadas
    saldo_pendiente: float  # Saldo restante por pagar
    estado_prestamo: str  # "activo", "parcial", "saldado"
    looker: int  # Indicador para Looker Studio (0 o 1)
    latitud: Optional[float] = None  # Coordenada geográfica
    longitud: Optional[float] = None  # Coordenada geográfica
    fuente_gps: str = "none"  # "live", "last_known", "none"
    mensaje_raw: str = ""  # Mensaje original del banco (auditoría)
    status: str = "consolidado"  # "consolidado", "pendiente"
    sincronizado: int = 0  # 0 = no sincronizado, 1 = sincronizado
    intentos_sync: int = 0  # Contador de reintentos
    ultimo_error_sync: str = ""  # Último error en texto


@dataclass
class NotificacionCruda:
    """Notificación recibida tal cual del banco antes de procesar."""
    id: int
    recibido_en: float  # Marca de tiempo epoch
    paquete: str  # Nombre paquete Android
    app: str  # Aplicación (Yape, Interbank, etc.)
    dispositivo: str
    titulo: str  # Título de la notificación
    cuerpo: str  # Mensaje completo
    id_transaccion_vinculada: Optional[str] = None  # FK opcional a transacciones
    resultado_proceso: str = "pendiente"  # "consolidada", "duplicado", "ignorada"


@dataclass
class AbonoPrestamo:
    """Historial de pagos parciales a deudas."""
    id: int
    id_transaccion_prestamo: str  # FK a la transacción de la deuda
    id_transaccion_ingreso: str  # FK al abono/ingreso que paga la deuda
    fecha_abono: str  # Fecha del abono
    monto_abono: float  # Monto pagado
    saldo_restante: float  # Saldo después del abono
    nota: str = ""  # Observaciones adicionales
