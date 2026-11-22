"""BBVAAdapter - Adaptador para notificaciones BBVA.

BBVA envía notificaciones genéricas sin detalles explícitos en el texto,
por lo que el proceso solicita de forma guiada al usuario:
1. Tipo de movimiento (Ingreso o Gasto)
2. Monto
3. Persona o comercio
4. Motivo"""

import uuid
import re
from datetime import datetime


class BBVAAdapter:
    """Adaptador para notificaciones BBVA."""

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
        En este adaptador, simulamos esa solicitud y construimos el diccionario."""
        mensaje = datos_crudos.get("content") or datos_crudos.get("message", "")

        # 1. Extraer monto si viene en el mensaje (aunque BBVA suele no incluírlo)
        monto = 0.0
        monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
        if monto_match:
            monto_str = monto_match.group(1)
            # En formato peruano, el punto es decimal para números normales
            # Pero BBVA a veces formatea de manera distinta, intentemos limpiar
            try:
                # Primero intentamos directo
                monto = float(monto_str)
            except ValueError:
                # Si falla, quitar puntos de miles y reemplazar coma por punto
                monto_str_limpio = monto_str.replace(".", "").replace(",", ".")
                try:
                    monto = float(monto_str_limpio)
                except ValueError:
                    monto = 0.0

        # 2. Tipo: indeterminado - siempre se solicitará al usuario
        tipo = "indeterminado"

        # 3. Destinatario: indeterminado
        destinatario = "por definir"

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
                # Si no hay cuando, usar fecha actual
                fecha_hora = datetime.now().isoformat()
        else:
            fecha_hora = datetime.now().isoformat()

        # 6. Constructar diccionario normalizado
        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": destinatario,
            "event_id": event_id,
            "canal": "bbva",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": None,  # Siempre None - se solicitará al usuario
            "fuente": "por definir",
            "origen_paquete": (
                datos_crudos.get("packageName")
                or datos_crudos.get("package")
                or datos_crudos.get("paquete", "")
            ),
            "titulo_visual": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "timestamp_epoch": datos_crudos.get("when", datos_crudos.get("timestamp", 0)),
        }

        return normalizado