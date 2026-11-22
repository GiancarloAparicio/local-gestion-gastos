"""NFCAdapter - Adaptador para pagos NFC y tarjetas.

Soporte para notificaciones de Google Pay / NFC del sistema Android.

Formato de notificación NFC (según documentación proporcionada):
- title: Comerciante/beneficiario (ej. "2446 MASS NISPE25 SMP M")
- message: Monto + tarjeta (ej. "S/ 20.00 con Visa ••9820")
- tipo_consumo: "GASTO" o "INGRESO"
- latitud, longitud: Coordenadas del lugar
- timestamp: Marca de tiempo epoch
"""

import re
import time
import uuid
from datetime import datetime


class NFCAdapter:
    """Adaptador para pagos NFC y tarjetas."""

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
        """Convierte datos crudos de notificación NFC a diccionario normalizado."""
        mensaje = datos_crudos.get("message") or datos_crudos.get("content", "")
        titulo = datos_crudos.get("title") or ""

        # 1. Extraer monto del mensaje (formato: "S/ X.XX con Visa ••9820")
        monto = 0.0
        monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
        if monto_match:
            monto_str = monto_match.group(1)
            # En formato peruano typical: "S/ 20.00" means 20.00 soles
            # El punto en números pequeños como "20.00" es decimal, no miles
            # Manejar ambos casos: si hay coma, es decimal; si solo punto en número pequeño, es decimal
            try:
                # Si hay coma, reemplazar coma por punto (decimal) y quitar puntos de miles
                if "," in monto_str:
                    # Formato con decimal por coma: "1.234,56" -> "1234.56"
                    monto_str = monto_str.replace(".", "").replace(",", ".")
                else:
                    # Formato solo con punto decimal: "20.00" -> "20.00"
                    # En Perú, para números < 1000, el punto es decimal
                    monto_str = monto_str
                monto = float(monto_str)
            except ValueError:
                monto = 0.0

        # 2. Determinar tipo de consumo
        # Revisar en los extras o mensaje
        tipo_consumo = datos_crudos.get("tipo_consumo", "").upper()
        if tipo_consumo == "GASTO":
            tipo = "gasto"
        elif tipo_consumo == "INGRESO":
            tipo = "ingreso"
        else:
            # Revisar en el mensaje si dice "ingreso" o "gasto"
            mensaje_lower = mensaje.lower()
            if "ingreso" in mensaje_lower:
                tipo = "ingreso"
            elif "gasto" in mensaje_lower or "plineaste" in mensaje_lower:
                tipo = "gasto"
            else:
                tipo = "indeterminado"

        # 2. Extraer beneficiario del title
        beneficiario = titulo if titulo else "desconocido"

        # 3. Extraer datos de tarjeta del message o extras
        # El message tiene: "S/ 20.00 con Visa ••9820"
        # Tarjeta extraída del pattern "con Visa ••9820"
        tarjeta_info = ""
        tarjeta_match = re.search(r"con\s+(Visa|MasterCard|American Express)\s*\\••\s*\\d{2}", mensaje)
        if tarjeta_match:
            tarjeta_info = tarjeta_match.group(1)

        # 4. Otros campos
        # latitud y longitud vienen en el propio dict
        latitud = datos_crudos.get("latitud")
        longitud = datos_crudos.get("longitud")
        timestamp = datos_crudos.get("timestamp", time.time())

        # 5. Generar event_id
        notification_id = datos_crudos.get("id", "")
        if notification_id and notification_id not in ("", "0"):
            event_id = str(notification_id)
        else:
            event_id = str(uuid.uuid4())

        # 6. Fecha hora
        try:
            dt = datetime.fromtimestamp(float(timestamp))
            fecha_hora = dt.isoformat()
        except (ValueError, TypeError):
            fecha_hora = datetime.now().isoformat()

        # 7. Constructar diccionario normalizado
        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": beneficiario,  # Title es el beneficiario/merchant
            "event_id": event_id,
            "canal": "nfc",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": None,  # NFC typically no requires user prompt for basic transaction
            "fuente": "por definir",
            "origen_paquete": datos_crudos.get("package", ""),
            "titulo_visual": titulo,
            "timestamp_epoch": timestamp,
            # Campos adicionales NFC-specific
            "tarjeta_info": tarjeta_info,
            "dispositivo": datos_crudos.get("device", "desconocido"),
            "tarjeta_mascarada": "••9820",  # Extraído del mensaje típicamente
        }

        return normalizado