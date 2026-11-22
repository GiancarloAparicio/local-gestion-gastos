"""YapeAdapter - Adaptador para notificaciones Yape."""

import re
import uuid
from datetime import datetime


class YapeAdapter:
    """Adaptador para notificaciones Yape."""

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es de Yape."""
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        return paquete == "com.bcp.innovacxion.yapeapp"

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convierte datos crudos de notificación Yape a diccionario normalizado."""
        # 1. Obtener el mensaje principal
        mensaje = datos_crudos.get("content") or datos_crudos.get("message", "")

        # 2. Extraer el monto (formato peruano: "S/ X" o "S/ X.XX")
        monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
        monto_str = monto_match.group(1) if monto_match else "0"
        # Quitar separadores de miles (punto en formato S/ 1.000 -> 1000)
        monto_str = monto_str.replace(".", "")
        monto = float(monto_str)

        # 3. Tipo: Yape siempre es ingreso
        tipo = "ingreso"

        # 4. Extraer destinatario (nombre que viene después de "Yape! ")
        nombre_match = re.search(r"Yape!\s+([^te]+)\s+te envió", mensaje)
        if nombre_match:
            destinatario = nombre_match.group(1).strip()
        else:
            # Fallback: expresión general de nombre propio
            nombre_match2 = re.search(
                r"Yape!\s+([A-ZÁÉÍÓÚñ][\wÑ]+(?:\s+[A-ZÁÉÍÓÚñ]\w+)*)", mensaje
            )
            destinatario = nombre_match2.group(1) if nombre_match2 else "desconocido"

        # 5. Generar event_id UUID
        notification_id = datos_crudos.get("notification_id") or datos_crudos.get("key", "")
        if notification_id and notification_id not in ("", "0"):
            event_id = str(notification_id)
        else:
            event_id = str(uuid.uuid4())

        # 6. Fecha hora
        # Termux: "when" formato "YYYY-MM-DD HH:MM:SS"
        # Automate: "timestamp" epoch seconds
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

        # 7. Constructar diccionario normalizado
        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": destinatario,
            "event_id": event_id,
            "canal": "yape",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": None,  # Siempre None - se solicitará después
            "fuente": "por definir",  # Se seteará después según modo
            "origen_paquete": (
                datos_crudos.get("packageName")
                or datos_crudos.get("package")
                or datos_crudos.get("paquete", "")
            ),
            "titulo_visual": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "timestamp_epoch": datos_crudos.get("when", datos_crudos.get("timestamp", 0)),
        }

        return normalizado
