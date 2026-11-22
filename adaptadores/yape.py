"""YapeAdapter - Adaptador para notificaciones Yape.

Soporte para notificaciones Yape.
- Detecta pagos entrantes desde la app Yape
- Extrae monto y destinatario del formato estructurado
- Genera event_id UUID para deduplicación
- Solicita motivo al usuario vía termux_api (contexto incluido)
"""

import re
import uuid
import time
from datetime import datetime

# Importar Termux API - SÓLO consumo, no lógica de diálogo propia
from modulios.termux_api import termux_api


class YapeAdapter:
    """Adaptador para notificaciones Yape."""

    def __init__(self):
        pass

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es de Yape."""
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        return paquete == "com.bcp.innovacxion.yapeapp"

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convierte datos crudos de notificación Yape a diccionario normalizado.

        Extrae monto, tipo (siempre ingreso) y destinatario del formato Yape.
        Solicita motivo al usuario vía termux_api con contexto.

        Formato esperado de notificación Yape:
        - message: "Yape! S/ X.00 a Nombre te envió plata"
        - title: "Yape"
        """
        # 1. Obtener el mensaje principal
        mensaje = datos_crudos.get("content") or datos_crudos.get("message", "")

        # 2. Extraer el monto (formato peruano: "S/ X" o "S/ X.XX")
        monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
        if monto_match:
            monto_str = monto_match.group(1)
            # En formato Yape, el punto es decimal (S/ 1.00 = 1.00 soles)
            try:
                monto = float(monto_str.replace(".", ""))  # Quitar punto de miles si existe
                # Asegurar que sea positivo
                if monto <= 0:
                    monto = 0.0
            except ValueError:
                monto = 0.0
        else:
            monto = 0.0

        # 2. Solicitar destinatario usando termux_api con contexto
        # El destinatario viene después de "Yape! " y antes de " te envió plata"
        destinatario = self._obtener_destinatario_yape(mensaje)

        # 3. Tipo: Yape siempre es ingreso
        tipo = "ingreso"

        # 4. Generar event_id UUID
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
                # Ya es formato string (Termux)
                fecha_hora = when
        else:
            fecha_hora = datetime.now().isoformat()

        # 6. Solicitar motivo usando termux_api con contexto Yape
        # Construimos el contexto: título="Yape", es_ingreso=True
        motivo = termux_api.solicitar_motivo_contexto(
            es_gasto=False,  # Yape siempre es ingreso
            titulo_notificacion="Yape",
            app_nombre="Yape"
        )

        # 7. Constructar diccionario normalizado
        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": destinatario,
            "event_id": event_id,
            "canal": "yape",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": motivo,  # Solicitado vía termux_api con contexto
            "fuente": "por definir",
            "origen_paquete": (
                datos_crudos.get("packageName")
                or datos_crudos.get("package")
                or datos_crudos.get("paquete", "")
            ),
            "titulo_visual": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "timestamp_epoch": datos_crudos.get("when", datos_crudos.get("timestamp", time.time())),
        }

        return normalizado

    def _obtener_destinatario_yape(self, mensaje: str) -> str:
        """Obtiene el destinatario del mensaje Yape usando regex.

        Intenta extraer el nombre del mensaje Yape "Yape! S/ X.00 a Nombre te envió plata".
        Si no puede extraerlo, solicita al usuario vía termux_api.solicitar_motivo_contexto
        reutilizándolo para pedir el destinatario (usando el título "Yape" como contexto).

        Returns:
            Nombre del destinatario o "desconocido"
        """
        # Primero intentamos extraer el nombre del mensaje usando regex
        # Formato: "Yape! S/ X.00 a Juan te envió plata"
        nombre_match = re.search(r"Yape!\s+[S$]\s*[\d,.]+\s+a\s+([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})\s+te\s+envi", mensaje, re.IGNORECASE)
        if nombre_match:
            nombre_extraido = nombre_match.group(1).strip()
            if nombre_extraido and len(nombre_extraido) > 1:
                # Verificar que no sea ruido
                if not nombre_extraido.lower() in ["yape", "plata", "envi"]:
                    return nombre_extraido

        # Si no pudo extraer del mensaje, solicitar al usuario via termux_api
        # Reutilizamos la función solicitar_motivo_contexto pero solicitando el destinatario
        # Como el título es "Yape" y es ingreso, el mensaje se adaptará
        try:
            resultado = termux_api.mostrar_dialogo(
                widget="text",
                titulo="Destinatario Yape",
                mensaje="Nombre de la persona que recibió el dinero: ",
            )
            if resultado and "text" in resultado:
                nombre = resultado["text"].strip()
                if nombre:
                    return nombre
            return "desconocido"
        except Exception:
            return "desconocido"