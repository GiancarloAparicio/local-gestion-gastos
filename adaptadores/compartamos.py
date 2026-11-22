"""CompartamosAdapter - Adaptador para notificaciones Compartamos Financiera.

Soporte para notificaciones de Compartamos Financiera (solo ingresos).
Según documentación: solo maneja ingresos, validación por monto y ventana corta.

Formato esperado de notificación Compartamos:
- title: Beneficiario/Remitente
- message: Monto del ingreso
- type: "ingreso" (siempre)
"""

import re
import uuid
import time
import os
from datetime import datetime

# Importar Termux API para diálogos
from modulios.termux_api import termux_api


class CompartamosAdapter:
    """Adaptador para notificaciones Compartamos Financiera."""

    def __init__(self):
        # Tracking para deduplicación ventana corta (10 minutos por defecto)
        self._ultimos_ingresos = {}  # {event_id_short: timestamp}

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es de Compartamos."""
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        # Paquete de Compartamos Financiera
        return paquete == "pe.com.compartamos.bancamovil"

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convierte datos crudos de notificación Compartamos a diccionario normalizado.

        Características:
        - Solo procesa ingresos (no gastos)
        - Validación de duplicados en ventana corta (10 min)
        - Solicita remitente vía termux-dialog
        - Solicita motivo vía termux-dialog
        - Obtiene GPS con termux-location
        """
        # 1. Obtener el mensaje principal
        mensaje = datos_crudos.get("message") or datos_crudos.get("content", "")

        # 2. Extraer el monto (formato: "S/ X.XX" o "S/ X")
        monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
        if monto_match:
            monto_str = monto_match.group(1)
            # Formato peruano: el punto es decimal para números normales
            try:
                monto = float(monto_str)
                # Asegurar que sea positivo (solo ingresos)
                if monto <= 0:
                    monto = 0.0
            except ValueError:
                monto = 0.0
        else:
            monto = 0.0

        # 2. Solicitar remitente/beneficiario vía termux-dialog
        # Usar termux-dialog text para obtener el nombre del beneficiario
        beneficiario = self._solicitar_beneficiario_termux()

        # 3. Tipo: Compartamos siempre es ingreso
        tipo = "ingreso"

        # 4. Generar event_id UUID
        notification_id = datos_crudos.get("id", "")
        if notification_id and notification_id not in ("", "0"):
            event_id = str(notification_id)
        else:
            event_id = str(uuid.uuid4())

        # 5. Fecha hora
        when = datos_crudos.get("when") or datos_crudos.get("timestamp")
        if when:
            try:
                dt = datetime.fromtimestamp(float(when))
                fecha_hora = dt.isoformat()
            except (ValueError, TypeError):
                fecha_hora = when
        else:
            fecha_hora = datetime.now().isoformat()

        # 6. Validar duplicados en ventana corta
        # Revisar si ya existe un ingreso con mismo monto en ventana de 10 min
        es_duplicado = False
        timestamp_epoch = datos_crudos.get("when", datos_crudos.get("timestamp", time.time()))

        try:
            fecha_actual = datetime.fromtimestamp(float(timestamp_epoch))
            # Buscar en tracking reciente
            clave_busqueda = beneficiario[:8] if len(beneficiario) >= 8 else beneficiario
            if clave_busqueda in self._ultimos_ingresos:
                tiempo_ultimo = self._ultimos_ingresos[clave_busqueda]
                diferencia = (fecha_actual - tiempo_ultimo).total_seconds()
                # Ventana corta: 10 minutos = 600 segundos
                es_duplicado = diferencia < 600
            # Actualizar tracking
            self._ultimos_ingresos[clave_busqueda] = fecha_actual
        except (ValueError, TypeError):
            es_duplicado = False

        # 7. Constructar diccionario normalizado
        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": beneficiario,  # Remitente/beneficiario
            "event_id": event_id,
            "canal": "compartamos",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": self._solicitar_motivo_termux(),  # Solicitado vía termux-dialog
            "fuente": "por definir",
            "origen_paquete": datos_crudos.get("package", ""),
            "titulo_visual": datos_crudos.get("title", ""),
            "timestamp_epoch": timestamp_epoch,
            # Flags y metadatos Compartamos-specific
            "es_duplicado": es_duplicado,
            "es_solo_ingreso": True,  # Compartamos solo ingresos
        }

        return normalizado

    def _solicitar_beneficiario_termux(self) -> str:
        """Solicita el beneficiario/remitente usando termux-dialog.

        Returns:
            Nombre del beneficiario ingresado por el usuario
        """
        # Usar termux-dialog text para ingresar el beneficiario
        try:
            resultado = termux_api.mostrar_dialogo(
                widget="text",
                titulo="Beneficiario",
                mensaje="Nombre del beneficiario o remitente:",
            )

            if resultado and "text" in resultado:
                beneficiario = resultado["text"].strip()
                if beneficiario:
                    return beneficiario
                return "desconocido"
            else:
                return "desconocido"
        except Exception as e:
            logger_warning = None
            try:
                import logging
                logger_warning = logging.getLogger(__name__)
            except:
                pass
            # Fallback si termux-dialog falla
            return "desconocido"

    def _solicitar_motivo_termux(self) -> str:
        """Solicita el motivo usando termux-dialog.

        Returns:
            Motivo ingresado por el usuario
        """
        try:
            resultado = termux_api.mostrar_dialogo(
                widget="text",
                titulo="Motivo del movimiento",
                mensaje="¿Cuál fue el motivo de este ingreso?",
            )

            if resultado and "text" in resultado:
                motivo = resultado["text"].strip()
                if motivo:
                    return motivo
                return "Sin motivo especificado"
            else:
                return "Sin motivo especificado"
        except Exception as e:
            # Fallback: retornar motivo por defecto
            return "Sin motivo especificado"