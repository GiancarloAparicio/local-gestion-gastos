"""BBVAAdapter - Adaptador para notificaciones BBVA.

BBVA envía notificaciones genéricas sin detalles explícitos en el texto,
por lo que el proceso solicita de forma guiada al usuario:
1. Tipo de movimiento (Ingreso o Gasto)
2. Monto
3. Persona o comercio
4. Motivo"""

import re
import uuid
import time
from datetime import datetime

# Importar Termux API - SÓLO consumo, sin lógica propia de diálogo
from modulios.termux_api import termux_api


class BBVAAdapter:
    """Adaptador para notificaciones BBVA."""

    def __init__(self):
        pass

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es de BBVA."""
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        # Los paquetes BBVA suelen comenzar con com.bbva o contener "bbva"
        return "bbva" in paquete.lower()

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convierte datos crudos de notificación BBVA a diccionario normalizado.

        A diferencia de otros bancos, BBVA requiere solicitar al usuario
        los datos completos ya que el mensaje no los contiene explícitamente.
        En este adaptador, solicitamos todos los datos vía termux_api con contexto."""

        # 1. Obtener el mensaje y determinar el tipo por palabras clave.
        mensaje = datos_crudos.get("content") or datos_crudos.get("message", "")
        mensaje_lower = mensaje.lower()
        titulo_notificacion = datos_crudos.get("title", datos_crudos.get("titulo", ""))

        if any(p in mensaje_lower for p in ("abono", "ingreso", "recibiste", "te depositaron")):
            tipo = "ingreso"
        elif any(p in mensaje_lower for p in ("consumo", "pago", "compra", "gasto", "debito")):
            tipo = "gasto"
        else:
            tipo = "gasto"

        # 2. Intentar extraer el monto del propio mensaje.
        monto = 0.0
        monto_match = re.search(r"S/\s*([\d.,]+)", mensaje)
        if monto_match:
            monto_str = monto_match.group(1).strip()
            try:
                if re.search(r"[.,]\d{1,2}$", monto_str):
                    monto = float(monto_str.replace(",", "."))
                else:
                    monto = float(monto_str.replace(".", "").replace(",", ""))
            except ValueError:
                monto = 0.0

        # Si el mensaje no trae monto, solicitarlo vía termux-dialog (solo Termux).
        if monto <= 0:
            monto_respuesta = termux_api.mostrar_dialogo(
                widget="counter",
                titulo="Monto BBVA",
                mensaje="¿Cuál es el monto? (en soles, ej. 20.00)",
                r="1,10000,1",
            )
            if monto_respuesta and "r" in monto_respuesta:
                try:
                    monto = float(monto_respuesta["r"])
                except ValueError:
                    monto = 0.0
            elif monto_respuesta and "text" in monto_respuesta:
                try:
                    monto = float(monto_respuesta["text"])
                except ValueError:
                    monto = 0.0

        # 3. Extraer destinatario del mensaje; si no, solicitarlo (solo Termux).
        destinatario = "por definir"
        nombre_match = re.search(r"(?:a|en)\s+([A-ZÁÉÍÓÚÑ][\wÑ\.\s]{2,40})", mensaje)
        if nombre_match:
            destinatario = nombre_match.group(1).strip().rstrip(".!,;:")
        else:
            destinatario_respuesta = termux_api.mostrar_dialogo(
                widget="text",
                titulo="Destinatario BBVA",
                mensaje="¿Quién es la persona o comercio? ",
            )
            if destinatario_respuesta and "text" in destinatario_respuesta:
                posible = destinatario_respuesta["text"].strip()
                if posible:
                    destinatario = posible

        # 3. Solicitar motivo vía termux_api con contexto
        motivo = termux_api.solicitar_motivo_contexto(
            es_gasto=False,
            titulo_notificacion=titulo_notificacion,
            app_nombre="BBVA"
        )

        # 4. Generar event_id
        notification_id = datos_crudos.get("notification_id") or datos_crudos.get("key", "")
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
                fecha_hora = datetime.now().isoformat()
        else:
            fecha_hora = datetime.now().isoformat()

        # 5. Constructar diccionario normalizado
        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": destinatario,
            "event_id": event_id,
            "canal": "bbva",
            "fecha_hora": fecha_hora,
            "mensaje_raw": datos_crudos.get("content") or datos_crudos.get("message", ""),
            "motivo": motivo,  # Solicitado vía termux_api con contexto BBVA
            "fuente": "por definir",
            "origen_paquete": (
                datos_crudos.get("packageName")
                or datos_crudos.get("package")
                or datos_crudos.get("paquete", "")
            ),
            "titulo_visual": titulo_notificacion,
            "timestamp_epoch": datos_crudos.get("when", datos_crudos.get("timestamp", 0)),
        }

        return normalizado