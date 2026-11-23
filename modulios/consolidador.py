"""Lógica de consolidación de notificaciones.

Este módulo implementa la ventana de consolidación para evitar que múltiples
alertas del mismo gasto disparen múltiples preguntas al usuario. Si una notificación
llega dentro de una ventana de tiempo definida (configurable, default 5 minutos),
se consolida en el registro existente en lugar de crear uno nuevo."""

import time
from datetime import datetime, timedelta


class Consolidador:
    """Clase que gestiona la consolidación de notificaciones en la ventana de tiempo."""

    def __init__(self, ventana_minutos: int = 5):
        self.ventana_minutos = ventana_minutos
        self.ventana_timedelta = timedelta(minutes=ventana_minutos)

    def debe_consolidar(self, fecha_hora_actual: datetime, fecha_hora_anterior: datetime) -> bool:
        """Determina si una nueva notificación debe consolidarse en una existente.

        Args:
            fecha_hora_actual: Marca de tiempo de la nueva notificación.
            fecha_hora_anterior: Marca de tiempo de la notificación anterior.

        Returns:
            True si la nueva notificación debe consolidarse (está dentro de la ventana),
            False si debe tratarse como un nuevo registro.
        """
        diferencia = fecha_hora_actual - fecha_hora_anterior
        return diferencia < self.ventana_timedelta

    def obtener_marcador_tiempo(self) -> datetime:
        """Obtiene la marca de tiempo actual menos la ventana de consolidación."""
        return datetime.now() - self.ventana_timedelta

    def verificar_duplicado_ventana(self, datos_nuevos) -> bool:
        """Determina si una nueva notificación debe consolidarse en una existente.
        
        Args:
            datos_nuevos: Diccionario con los datos de la nueva notificación
        
        Returns:
            True si la notificación debe consolidarse (duplicado en ventana),
            False si es un registro nuevo
        """
        # Versión simplificada: retornar False para que siempre sea un nuevo registro
        # En una implementación completa, compararía la fecha/hora de la notificación
        # previa con la actual usando self.ventana_timedelta
        return False


# Instancia global con configuración por defecto (5 minutos)
consolidador = Consolidador(ventana_minutos=5)
