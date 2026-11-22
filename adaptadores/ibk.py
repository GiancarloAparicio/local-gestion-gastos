"""IBKAdapter - Adaptador para notificaciones Interbank y Plin.

Soporte para notificaciones de Interbank Mobile Banking incluyendo:
- Transferencias de gasto (formato: "Plineaste S/ X.00 a Nombre")
- Ingresos Plin (formato: "Nombre te ha plineado S/ X.00")

Maneja validación de duplicados en ventana de 5 minutos.
"""

import re
import uuid
import time
from datetime import datetime

from modulios.consolidador import consolidador


class IBKAdapter:
    """Adaptador para notificaciones Interbank y Plin."""

    def __init__(self):
        # Track recent notifications for duplicate detection
        self._ultimos_gastos = {}  # {destinatario: timestamp}
        self._ultimos_ingresos = {}  # {remitente: timestamp}

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es de Interbank/Plin."""
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        return paquete == "pe.com.interbank.mobilebanking"

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convierte datos crudos de notificación Interbank/Plin a diccionario normalizado.

        Soporta ambos formatos:
        - Gasto: "Plineaste S/ X.00 a Nombre" (usuario envió dinero)
        - Ingreso: "Nombre te ha plineado S/ X.00" (recibió dinero)

        Incluye validación de duplicados en ventana de 5 minutos.
        """
        # 1. Obtener el mensaje principal
        mensaje = datos_crudos.get("content") or datos_crudos.get("message", "")

        # 2. Determinar si es gasto o ingreso basándose en el formato del mensaje
        mensaje_lower = mensaje.lower()

        es_gasto = False
        es_ingreso = False

        # Formato gasto: "plineaste s/ ..." (usuario envió)
        if "plineaste" in mensaje_lower:
            es_gasto = True
        # Formato ingreso: "... te ha plineado ..." (recibió dinero)
        elif "te ha plineado" in mensaje_lower:
            es_ingreso = True
        else:
            # Formato legacy o genérico
            es_gasto = "plineaste" in mensaje_lower or "transferencia" in mensaje_lower
            es_ingreso = "abonó" in mensaje_lower or "transferencia recibida" in mensaje_lower

        # 3. Extraer el monto (formato peruano: "S/ X" o "S/ X.XX")
        monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
        if monto_match:
            monto_str = monto_match.group(1)
            # En formato peruano, el punto es separador decimal (S/ 1.00 = 1.00 soles)
            try:
                monto = float(monto_str)
            except ValueError:
                # Si tiene puntos y comas, intentemos limpiarlo
                monto_str_limpio = monto_str.replace(".", "").replace(",", ".")
                monto = float(monto_str_limpio) if monto_str_limpio else 0.0
        else:
            monto = 0.0

        # 4. Extraer destinatario/remitente
        # Definimos el nombre basándose en el formato:
        # - Gasto: nombre que aparece DESPUÉS de "a " 
        # - Ingreso: nombre que aparece ANTES de " te ha plineado"
        destinatario = "desconocido"
        
        if es_gasto:
            # Formato gasto: "Plineaste S/ X.00 a Nombre Completo"
            # Buscar "a " seguido del nombre (hasta encontrar espacio o fin de línea)
            name_match = re.search(r"a\s+([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})", mensaje)
            if name_match:
                destinatario = name_match.group(1).strip()
                # Limpiar posibles ruidos finales
                destinatario = destinatario.rstrip(".!,;:")
        else:
            # Formato ingreso: "Nombre te ha plineado S/ X.00"
            # Buscar nombre al principio de la cadena o después de símbolos
            name_match = re.search(r"^([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})\s+te", mensaje)
            if name_match:
                destinatario = name_match.group(1).strip()
            else:
                # Alternativa: buscar después de inicio del mensaje hasta " te ha"
                alt_match = re.search(r"^([A-ZÁÉÍÓÚñ][\wÑ\s]{2,50})\s+te\s+ha", mensaje)
                if alt_match:
                    destinatario = alt_match.group(1).strip()
        
        # Limpiar nombres extraídos de basura
        if destinatario.lower() in ["plineaste", "test", "s/"] or len(destinatario) < 2:
            destinatario = "desconocido"
        # Quitar sufijos comunes de ruido
        for suffix in [" te ha", " te ha plineado", " S/ ", " ingreso", " gasto"]:
            if destinatario.lower().endswith(suffix.lower()):
                destinatario = destinatario[:-len(suffix)].strip()
                break

        # 5. Generar event_id UUID
        notification_id = datos_crudos.get("notification_id") or datos_crudos.get("key", "")
        if notification_id and notification_id not in ("", "0"):
            event_id = str(notification_id)
        else:
            event_id = str(uuid.uuid4())

        # 6. Fecha hora
        when = datos_crudos.get("when") or datos_crudos.get("timestamp")
        if when:
            try:
                dt = datetime.fromtimestamp(float(when))
                fecha_hora = dt.isoformat()
            except (ValueError, TypeError):
                fecha_hora = when
        else:
            fecha_hora = datetime.now().isoformat()

        # 7. Validar duplicados en ventana de tiempo
        timestamp_epoch = datos_crudos.get("when", datos_crudos.get("timestamp", time.time()))
        try:
            fecha_actual = datetime.fromtimestamp(float(timestamp_epoch))

            # Determinar qué diccionario de tracking usar basado en tipo
            if es_gasto:
                clave_busqueda = destinatario[:8] if len(destinatario) >= 8 else destinatario
                if clave_busqueda in self._ultimos_gastos:
                    tiempo_ultimo = self._ultimos_gastos[clave_busqueda]
                    diferencia = (fecha_actual - tiempo_ultimo).total_seconds()
                    es_duplicado = diferencia < 300  # 5 minutos = 300 segundos
                else:
                    es_duplicado = False
                # Actualizar tracking de gastos
                self._ultimos_gastos[clave_busqueda] = fecha_actual
            else:
                clave_busqueda = destinatario[:8] if len(destinatario) >= 8 else destinatario
                if clave_busqueda in self._ultimos_ingresos:
                    tiempo_ultimo = self._ultimos_ingresos[clave_busqueda]
                    diferencia = (fecha_actual - tiempo_ultimo).total_seconds()
                    es_duplicado = diferencia < 300  # 5 minutos = 300 segundos
                else:
                    es_duplicado = False
                # Actualizar tracking de ingresos
                self._ultimos_ingresos[clave_busqueda] = fecha_actual
        except (ValueError, TypeError):
            es_duplicado = False

        # 8. Constructar diccionario normalizado
        normalizado = {
            "monto": monto,
            "tipo": "gasto" if es_gasto else "ingreso",
            "destinatario": destinatario,
            "event_id": event_id,
            "canal": "interbank",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": None,
            "fuente": "por definir",
            "origen_paquete": (
                datos_crudos.get("packageName")
                or datos_crudos.get("package")
                or datos_crudos.get("paquete", "")
            ),
            "titulo_visual": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "timestamp_epoch": timestamp_epoch,
            # Flags para control de duplicados
            "es_duplicado": es_duplicado,
            "consolidado_en": None,
        }

        return normalizado

    def verificar_duplicado(self, destinatario: str, timestamp_actual: float, es_gasto: bool) -> bool:
        """Verifica si una notificación es duplicada.

        Args:
            destinatario: Nombre de la persona
            timestamp_actual: Marca de tiempo epoch
            es_gasto: True si es gasto, False si es ingreso

        Returns:
            True si es duplicado (dentro de ventana de 5 min)
        """
        try:
            fecha_actual = datetime.fromtimestamp(timestamp_actual)

            if es_gasto:
                if destinatario in self._ultimos_gastos:
                    tiempo_ultimo = self._ultimos_gastos[destinatario]
                    diferencia = abs((fecha_actual - tiempo_ultimo).total_seconds())
                    return diferencia < 300  # 5 minutos
            else:
                if destinatario in self._ultimos_ingresos:
                    tiempo_ultimo = self._ultimos_ingresos[destinatario]
                    diferencia = abs((fecha_actual - tiempo_ultimo).total_seconds())
                    return diferencia < 300  # 5 minutos

            return False
        except (ValueError, TypeError):
            return False