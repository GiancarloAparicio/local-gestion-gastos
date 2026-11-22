"""NFCAdapter - Adaptador para pagos NFC y tarjetas.

Soporte para notificaciones de Google Pay / NFC del sistema Android.

Formato de notificación NFC (según documentación proporcionada):
- title: Comerciante/beneficiario (ej. "2446 MASS NISPE25 SMP M")
- message: Monto + tarjeta (ej. "S/ 20.00 con Visa ••9820")
- tipo_consumo: "GASTO" o "INGRESO"
- latitud, longitud: Coordenadas del lugar
- timestamp: Marca de tiempo epoch"""

import re
import uuid
import time
from datetime import datetime

# Importar Termux API - SÓLO consumo, sin lógica propia de diálogo
from modulios.termux_api import termux_api


class NFCAdapter:
    """Adaptador para pagos NFC y tarjetas."""

    def __init__(self):
        pass

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es de NFC/billetera digital."""
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        # NFC wallet package
        return paquete == "com.google.android.apps.walletnfcrel"

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convierte datos crudos de notificación NFC a diccionario normalizado.

        Extrae beneficiario del title, monto y datos de tarjeta del message,
        y solicita el motivo al usuario vía termux_api con contexto.

        Formato esperado de notificación NFC:
        - title: Beneficiario/merchant (ej. "2446 MASS NISPE25 SMP M")
        - message: Monto + datos tarjeta (ej. "S/ 20.00 con Visa ••9820")
        - tipo_consumo: "GASTO" o "INGRESO" (en extras o mensaje)
        - latitud, longitud: Coordenadas del lugar
        - timestamp: Marca de tiempo epoch
        """
        # 1. Obtener el mensaje principal
        mensaje = datos_crudos.get("message") or datos_crudos.get("content", "")

        # 2. Extraer monto del mensaje (formato: "S/ X.XX con Visa ••9820")
        monto = 0.0
        monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
        if monto_match:
            monto_str = monto_match.group(1)
            # En formato peruano, el punto es decimal para números normales (S/ 20.00 = 20.00)
            try:
                monto = float(monto_str)
            except ValueError:
                # Si tiene miles, intentar limpiar
                monto_str_limpio = monto_str.replace(".", "").replace(",", ".")
                try:
                    monto = float(monto_str_limpio)
                except ValueError:
                    monto = 0.0
        else:
            # Si no hay monto en el mensaje, solicitaremos al usuario vía termux_dialog
            monto = None  # Indicaremos que faltó el monto

        # 2. Extraer beneficiario del title (formato: "2446 MASS NISPE25 SMP M")
        beneficiario = datos_crudos.get("title") or ""

        # 3. Determinar tipo de consumo (gasto/ingreso)
        tipo_consumo = datos_crudos.get("tipo_consumo", "").upper()
        if tipo_consumo == "GASTO":
            tipo = "gasto"
        elif tipo_consumo == "INGRESO":
            tipo = "ingreso"
        else:
            # Revisar en el mensaje si dice "ingreso" o "gasto"
            mensaje_lower = mensaje.lower() if mensaje else ""
            if "ingreso" in mensaje_lower:
                tipo = "ingreso"
            elif "gasto" in mensaje_lower or "plineaste" in mensaje_lower:
                tipo = "gasto"
            else:
                tipo = "indeterminado"

        # 3. Solicitar motivo al usuario vía termux_api con contexto NFC
        # Pasamos el título de la notificación y el nombre de la app para contexto
        motivo = termux_api.solicitar_motivo_contexto(
            es_gasto=(tipo == "gasto"),
            titulo_notificacion=datos_crudos.get("title", datos_crudos.get("titulo", "")),
            app_nombre="NFC"
        )

        # 4. Generar event_id UUID
        notification_id = datos_crudos.get("id", "")
        if notification_id and notification_id not in ("", "0"):
            event_id = str(notification_id)
        else:
            event_id = str(uuid.uuid4())

        # 5. Fecha hora
        when = datos_crudos.get("timestamp", datos_crudos.get("when"))
        if when:
            try:
                dt = datetime.fromtimestamp(float(when))
                fecha_hora = dt.isoformat()
            except (ValueError, TypeError):
                # Si viene como string formateado (Termux), usarlo directamente
                fecha_hora = str(when)
        else:
            fecha_hora = datetime.now().isoformat()

        # 5. Constructar diccionario normalizado
        normalizado = {
            "monto": monto if monto is not None else 0.0,  # Si fue None, pondremos 0
            "tipo": tipo,
            "destinatario": beneficiario,  # Title es el beneficiario/merchant
            "event_id": event_id,
            "canal": "nfc",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": motivo,  # Solicitado vía termux_api con contexto NFC
            "fuente": "por definir",
            "origen_paquete": datos_crudos.get("package", ""),
            "titulo_visual": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "timestamp_epoch": when if when else time.time(),
            # Campos adicionales NFC-specific
            "tarjeta_info": "",  # Se extraería del pattern "con Visa ••9820" si es necesario
            "dispositivo": datos_crudos.get("device", "desconocido"),
        }

        return normalizado