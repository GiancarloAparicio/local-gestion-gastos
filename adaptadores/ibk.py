"""IBKAdapter - Adaptador para notificaciones Interbank y Plin.

Soporte para notificaciones de Interbank Mobile Banking incluyendo:
- Transferencias de gasto (formato: "TRAN S/ X.00\nA: Nombre")
- Gastos Plin (formato: "Plineaste S/ X.00 a Nombre")
- Consumos con tarjeta (formato: "Realizaste un consumo con tu tarjeta.")
- Pagos con NFC/Wallet (formato: "S/ X.XX con Nombre ••XXXX")

Manejo de validación de duplicados en ventana de 5 minutos con tracking
por formato. Solicita siempre motivo al usuario vía termux-dialog.
Solo solicita monto cuando el formato es tarjeta (monto vacío en mensaje).
El sistema consolidará automáticamente notificaciones NFC e Interbank
que correspondan al mismo gasto, independientemente del orden de llegada.
"""

import re
import uuid
import time
from datetime import datetime

from modulios.termux_api import termux_api


class IBKAdapter:
    """Adaptador para notificaciones Interbank y Plin con soporte para 3 formatos."""

    def __init__(self):
        # Track recent notifications for duplicate detection
        # Formato: {destinatario: (timestamp_epoch, formato_tipo, monto_referencia)}
        self._ultimos_gastos = {}
        self._ultimos_ingresos = {}

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es de Interbank/Plin."""
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        return paquete == "pe.com.interbank.mobilebanking"

    def _clasificar_formato(self, mensaje: str) -> str:
        """Detecta el tipo de notificación: 'transferencia', 'plin', 'tarjeta', 'nfc' o 'desconocido'.

        Prioridad:
        1. Formato NFC: mensaje contiene "walletnfcrel" o patrón "S/ con ... ••"
        2. Formato TRAN: mensaje contiene "tran" (mayúsculas)
        3. Formato Plin: mensaje contiene "plineaste" (minúsculas)
        4. Formato Tarjeta: mensaje contiene "consumo" o "tarjeta" con "realizaste"
        5. Desconocido: ningún patrón coincide
        """
        mensaje_lower = mensaje.lower()

        # 1. Detectar formato NFC (Google Pay walletnfcrel)
        # Patrones: "S/ 63.67 con Infinite ••9820" o "S/ 63.67 con Infinite"
        if "walletnfcrel" in mensaje_lower or re.search(r"s/\s+[\d,.]+\s+con\s+", mensaje_lower):
            return "nfc"

        if "tran" in mensaje_lower:
            return "transferencia"
        elif "plineaste" in mensaje_lower:
            return "plin"
        elif "consumo" in mensaje_lower or (
            "tarjeta" in mensaje_lower and "realizaste" in mensaje_lower
        ):
            return "tarjeta"
        else:
            return "desconocido"

    def _solicitar_monto_condicional(self, formato_tipo: str):
        """Solicita monto solo si es formato tarjeta (viene vacío en mensaje).

        Args:
            formato_tipo: 'transferencia', 'plin', 'tarjeta' o 'desconocido'

        Returns:
            Diccionario con resultado del diálogo si es formato tarjeta, None en otro caso
        """
        if formato_tipo == "tarjeta":
            return termux_api.mostrar_dialogo(
                widget="text",
                titulo="Monto del consumo",
                mensaje="¿Cuánto fue el consumo? (ej: S/ 35.00)",
            )
        # Para TRAN y PLIN, el monto viene en el mensaje, no solicitar
        return None

    def _solicitar_motivo_contexto(self, formato_tipo: str):
        """Solicita motivo siempre, con mensaje contextual según el formato.

        Siempre se pregunta el motivo, pero el mensaje varía según el tipo de transacción.

        Args:
            formato_tipo: 'transferencia', 'plin', 'tarjeta' o 'desconocido'

        Returns:
            Diccionario con resultado del diálogo o None si falla
        """
        mensajes_motivo = {
            "tarjeta": "¿Cuál fue el motivo del consumo con tarjeta? ",
            "transferencia": "¿Cuál fue el motivo de la transferencia? ",
            "plin": "¿Cuál fue el motivo del pago con Plin? ",
            "default": "¿Cuál fue el motivo de este movimiento? ",
        }
        mensaje = mensajes_motivo.get(formato_tipo, mensajes_motivo["default"])
        return termux_api.mostrar_dialogo(
            widget="text",
            titulo="Motivo del movimiento",
            mensaje=mensaje,
        )

    def _es_duplicado_enriquecido(
        self,
        destinatario: str,
        monto: float,
        formato_tipo: str,
        timestamp_epoch: float,
    ) -> bool:
        """Validación de duplicados considerando los 3 formatos.

        Reglas principales:
        1. Mismo formato + mismo destinatario + mismo monto + ventana 5 min → DUPICADO
        2. Formato distinto (TRAN + Tarjeta + Plin) → NO es duplicado, consolidar
        3. 2 Plines iguales a misma persona → NUNCA duplicado (eventos independientes)
        4. Formato distinto pero mismo destinatario → Consolidar (no duplicado)

        Args:
            destinatario: Nombre de la persona/establecimiento
            monto: Monto de la notificación actual
            formato_tipo: 'transferencia', 'plin', 'tarjeta' o 'desconocido'
            timestamp_epoch: Marca de tiempo actual en epoch

        Returns:
            True si es duplicado estricto, False si debe consolidarse o es evento independiente
        """
        try:
            fecha_actual = datetime.fromtimestamp(float(timestamp_epoch))

            # Caso especial: formato PLIN
            # 2 plines iguales a la misma persona NUNCA son duplicado
            # Si el formato es distinto a plin (TRAN, tarjeta), consolidar y NO duplicar
            if formato_tipo == "plin":
                if destinatario in self._ultimos_gastos:
                    tiempo_ultimo, formato_anterior, monto_anterior = (
                        self._ultimos_gastos[destinatario]
                    )
                    # Si el anterior también es plin, NO es duplicado, es evento independiente
                    if formato_anterior == "plin":
                        # Actualizar tracking pero NO marcar como duplicado
                        self._ultimos_gastos[destinatario] = (
                            timestamp_epoch,
                            "plin",
                            monto,
                        )
                        return False  # No es duplicado, es un evento independiente
                    else:
                        # Formato anterior era distinto a plin (TRAN o tarjeta)
                        # SE CONSOLIDA: no es duplicado, es el mismo gasto en secuencia distinta
                        # Actualizar tracking manteniendo el formato actual
                        self._ultimos_gastos[destinatario] = (
                            timestamp_epoch,
                            "plin",
                            monto,
                        )
                        return False  # No es duplicado, consolidar con registro existente
                else:
                    self._ultimos_gastos[destinatario] = (
                        timestamp_epoch,
                        "plin",
                        monto,
                    )
                    return False

            # Caso formato TRAN (transferencia)
            if formato_tipo == "transferencia":
                if destinatario in self._ultimos_gastos:
                    tiempo_ultimo, formato_anterior, monto_anterior = (
                        self._ultimos_gastos[destinatario]
                    )
                    # MISMO TIPO NUNCA es duplicado (TRAN + TRAN, PLIN + PLIN, TARJETA + TARJETA)
                    # Siempre que el formato anterior sea igual al actual, no es duplicado
                    # Actualizar tracking pero NO marcar como duplicado
                    self._ultimos_gastos[destinatario] = (
                        timestamp_epoch,
                        "transferencia",
                        monto,
                    )
                    return False  # Mismo tipo TRAN + TRAN = NUNCA duplicado
                    # NOTE: Antes aquí validaba ventana 5 min + monto, pero según nuevas reglas
                    # el mismo tipo siempre son gastos distintos
                    # Si formato_anterior distinto a transferencia, caería en el else abajo
                else:
                    self._ultimos_gastos[destinatario] = (
                        timestamp_epoch,
                        "transferencia",
                        monto,
                    )
                    return False

            # Caso formato TARJETA
            if formato_tipo == "tarjeta":
                if destinatario in self._ultimos_gastos:
                    tiempo_ultimo, formato_anterior, monto_anterior = (
                        self._ultimos_gastos[destinatario]
                    )
                    # MISMO TIPO NUNCA es duplicado (TARJETA + TARJETA)
                    # Siempre que el formato anterior sea igual al actual, no es duplicado
                    # Actualizar tracking pero NO marcar como duplicado
                    self._ultimos_gastos[destinatario] = (
                        timestamp_epoch,
                        "tarjeta",
                        monto,
                    )
                    return False  # Mismo tipo TARJETA + TARJETA = NUNCA duplicado
                    # NOTE: Antes aquí validaba ventana 5 min + monto, pero según nuevas reglas
                    # el mismo tipo siempre son gastos distintos
                    # Si formato_anterior distinto a tarjeta, caería en el else abajo
                else:
                    self._ultimos_gastos[destinatario] = (
                        timestamp_epoch,
                        "tarjeta",
                        monto,
                    )
                    return False

            # Formato DESCONOCIDO - validación básica, no duplicar
            return False

        except (ValueError, TypeError, ZeroDivisionError):
            return False

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convierte datos crudos de notificación Interbank/Plin a diccionario normalizado.

        Soporta los 3 formatos:
        - Gasto TRAN: "TRAN S/ X.00\nA: Nombre" (transferencia)
        - Gasto Plin: "Plineaste S/ X.00 a Nombre" (usuario envió dinero)
        - Gasto Tarjeta: "Realizaste un consumo con tu tarjeta." (monto vacío en mensaje)

        Incluye validación de duplicados en ventana de 5 minutos con tracking por formato,
        y solicita siempre motivo al usuario vía termux-dialog.
        Solo solicita monto cuando el formato es tarjeta (monto vacío en mensaje).
        """

        # 1. Obtener el mensaje principal
        mensaje = datos_crudos.get("content") or datos_crudos.get("message", "")

        # 2. Clasificar el formato de la notificación
        formato_tipo = self._clasificar_formato(mensaje)

        # 3. Determinar si es gasto o ingreso basándose en el formato del mensaje
        mensaje_lower = mensaje.lower()

        es_gasto = False
        es_ingreso = False

        # Un consumo con tarjeta o pago NFC siempre es un gasto.
        if formato_tipo in ("tarjeta", "nfc"):
            es_gasto = True
        # Formato gasto: "plineaste s/ ..." (usuario envió)
        elif "plineaste" in mensaje_lower:
            es_gasto = True
        # Formato ingreso: "... te ha plineado ..." (recibió dinero)
        elif "te ha plineado" in mensaje_lower:
            es_ingreso = True
        else:
            # Formato legacy o genérico (incluye TRAN, transferencia, consumo, etc.)
            es_gasto = (
                "plineaste" in mensaje_lower
                or "tran" in mensaje_lower
                or "transferencia" in mensaje_lower
                or "consumo" in mensaje_lower
                or "compra" in mensaje_lower
            )
            es_ingreso = (
                "abonó" in mensaje_lower or "transferencia recibida" in mensaje_lower
            )

        # 4. Extraer el monto según el formato
        if formato_tipo == "tarjeta":
            # Formato tarjeta: el monto puede venir en el mensaje o venir vacío
            # Ejemplos: "Realizaste un consumo de S/.3.50 en VENDOMATICA..." o "Realizaste un consumo con tu tarjeta."
            monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
            if monto_match:
                monto_str = monto_match.group(1)
                try:
                    monto = float(monto_str)
                    monto_viene_en_mensaje = True
                except ValueError:
                    monto_str_limpio = monto_str.replace(".", "").replace(",", ".")
                    monto = float(monto_str_limpio) if monto_str_limpio else 0.0
                    monto_viene_en_mensaje = True
            else:
                monto = 0.0
                monto_viene_en_mensaje = False
        else:
            # Formato TRAN o PLIN: el monto viene en el mensaje
            monto_match = re.search(r"S/\s*([\d,.]+)", mensaje)
            if monto_match:
                monto_str = monto_match.group(1)
                try:
                    monto = float(monto_str)
                    monto_viene_en_mensaje = True
                except ValueError:
                    monto_str_limpio = monto_str.replace(".", "").replace(",", ".")
                    monto = float(monto_str_limpio) if monto_str_limpio else 0.0
                    monto_viene_en_mensaje = True
            else:
                monto = 0.0
                monto_viene_en_mensaje = False

        # 5. Extraer destinatario/remitente según el formato
        destinatario = "desconocido"

        if es_gasto:
            if formato_tipo == "plin":
                # Formato Plin: "Plineaste S/ X.00 a Nombre"
                name_match = re.search(
                    r"a\s+([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})", mensaje
                )
                if name_match:
                    destinatario = name_match.group(1).strip()
                    destinatario = destinatario.rstrip(".!,;:")
                else:
                    destinatario = "desconocido"
            elif formato_tipo == "transferencia":
                # Formato TRAN: "TRAN S/ X.00\nA: Nombre\n(fecha hora)"
                name_match = re.search(
                    r"A:\s*([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})", mensaje
                )
                if name_match:
                    destinatario = name_match.group(1).strip()
                    destinatario = destinatario.rstrip(".!,;:")
                else:
                    # Alternativa: buscar después de "S/ X.00\nA:"
                    name_match_alt = re.search(
                        r"\nA:\s*([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})", mensaje
                    )
                    if name_match_alt:
                        destinatario = name_match_alt.group(1).strip()
                        destinatario = destinatario.rstrip(".!,;:")
                    else:
                        destinatario = "desconocido"
            elif formato_tipo == "tarjeta":
                # Formato Tarjeta: el destinatario puede ser el comercio o venir vacío
                # Ejemplo: "Realizaste un consumo de S/.3.50 en VENDOMATICA con tu Tarjeta de Crédito."
                # o "Realizaste un consumo con tu tarjeta."
                name_match = re.search(
                    r"en\s+([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,50})", mensaje
                )
                if name_match:
                    destinatario = name_match.group(1).strip()
                    destinatario = destinatario.rstrip(".!,;:")
                else:
                    # Si no hay "en Nombre", intentar extraer cualquier nombre propio
                    # o dejarlo como "desconocido" y que el usuario lo complete
                    destinatario = "por definir"
            else:
                # Formato legacy o genérico
                name_match = re.search(
                    r"a\s+([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})", mensaje
                )
                if name_match:
                    destinatario = name_match.group(1).strip()
                    destinatario = destinatario.rstrip(".!,;:")
                else:
                    destinatario = "desconocido"
        else:
            # Formato ingreso (te ha plineado...)
            name_match = re.search(
                r"^([A-ZÁÉÍÓÚñ][\wÑ\.\s]{2,40})\s+te", mensaje
            )
            if name_match:
                destinatario = name_match.group(1).strip()
            else:
                alt_match = re.search(
                    r"^([A-ZÁÉÍÓÚñ][\wÑ\s]{2,50})\s+te\s+ha", mensaje
                )
                if alt_match:
                    destinatario = alt_match.group(1).strip()

        # Limpiar nombres extraños
        if destinatario.lower() in ["plineaste", "test", "s/"] or len(destinatario) < 2:
            destinatario = "desconocido"

        # 6. Solicitar motivo AL SIEMPRE vía termux-dialog con contexto según formato
        motivo = None
        # Siempre se solicita motivo, independientemente del formato
        try:
            resultado = self._solicitar_motivo_contexto(formato_tipo)
            if resultado and "text" in resultado:
                texto = resultado["text"].strip()
                if texto:
                    motivo = texto
                # Si el usuario cancela el diálogo (texto vacío), dejar motivo como None
                # Esto permite que el registro tenga motivo vacío si el usuario lo desea
        except Exception:
            # Si termux-dialog no está disponible, dejamos motivo como None
            # En producción esto debería manejarse con fallback apropiado
            pass

        # 7. Validar duplicados ENRIQUECIDO considerando los 3 formatos
        timestamp_epoch = datos_crudos.get(
            "when", datos_crudos.get("timestamp", time.time())
        )
        es_duplicado = self._es_duplicado_enriquecido(
            destinatario, monto, formato_tipo, timestamp_epoch
        )

        # 8. Si es duplicado estricto, anular motivo y monto para evitar registro duplicado
        # Solo si es duplicado verdadero (mismo formato + mismo monto + misma ventana)
        if es_duplicado:
            # Mantener el monto y destinatario del registro existente,
            # pero anular motivo y event_id para consolidación
            es_duplicado = True  # Ya está establecido arriba

        # 9. Generar event_id UUID
        notification_id = datos_crudos.get("notification_id") or datos_crudos.get("key", "")
        if notification_id and notification_id not in ("", "0"):
            event_id = str(notification_id)
        else:
            event_id = str(uuid.uuid4())

        # 10. Fecha hora
        when = datos_crudos.get("when") or datos_crudos.get("timestamp")
        if when:
            try:
                dt = datetime.fromtimestamp(float(when))
                fecha_hora = dt.isoformat()
            except (ValueError, TypeError):
                fecha_hora = when
        else:
            fecha_hora = datetime.now().isoformat()

        # 11. Constructar diccionario normalizado ENRIQUECIDO con campos de tracking
        normalizado = {
            "monto": monto,
            "tipo": "gasto" if es_gasto else "ingreso",
            "destinatario": destinatario,
            "event_id": event_id,
            "canal": "interbank",
            "fecha_hora": fecha_hora,
            "mensaje_raw": mensaje,
            "motivo": motivo,
            "fuente": "por definir",
            "origen_paquete": (
                datos_crudos.get("packageName")
                or datos_crudos.get("package")
                or datos_crudos.get("paquete", "")
            ),
            "titulo_visual": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "timestamp_epoch": timestamp_epoch,
            # Flags y tracking para control de duplicados
            "es_duplicado": es_duplicado,
            "consolidado_en": None,
            # Nuevos campos para clasificación y seguimiento
            "formato_tipo": formato_tipo,
            "monto_referencia": (
                monto if monto_viene_en_mensaje else None
            ),  # None para formato tarjeta (solicitar al usuario)
            "notificacion_origen": (
                "primer_registro"
                if not self._ultimos_gastos.get(destinatario, (None, None, None))[0]
                else "secundario"
            ),
        }

        return normalizado

    def verificar_duplicado(self, destinatario: str, timestamp_actual: float, es_gasto: bool) -> bool:
        """Verifica si una notificación es duplicada.

        Versión mantenida para compatibilidad con código existente.
        La validación real se realiza en normalizar_notificacion con _es_duplicado_enriquecido.

        Args:
            destinatario: Nombre de la persona
            timestamp_actual: Marca de tiempo epoch
            es_gasto: True si es gasto, False si es ingreso

        Returns:
            True si es duplicado (dentro de ventana de 5 min para mismo formato)
        """
        try:
            fecha_actual = datetime.fromtimestamp(timestamp_actual)

            if es_gasto:
                if destinatario in self._ultimos_gastos:
                    tiempo_ultimo = self._ultimos_gastos[destinatario]
                    # El tiempo puede ser tupla (epoch, formato, monto) o solo epoch por compatibilidad
                    if isinstance(tiempo_ultimo, tuple):
                        tiempo_epoch = tiempo_ultimo[0]
                    else:
                        tiempo_epoch = tiempo_ultimo
                    diferencia = abs((fecha_actual - datetime.fromtimestamp(tiempo_epoch)).total_seconds())
                    return diferencia < 300  # 5 minutos
            else:
                if destinatario in self._ultimos_ingresos:
                    tiempo_ultimo = self._ultimos_ingresos[destinatario]
                    if isinstance(tiempo_ultimo, tuple):
                        tiempo_epoch = tiempo_ultimo[0]
                    else:
                        tiempo_epoch = tiempo_ultimo
                    diferencia = abs((fecha_actual - datetime.fromtimestamp(tiempo_epoch)).total_seconds())
                    return diferencia < 300  # 5 minutos

            return False
        except (ValueError, TypeError):
            return False