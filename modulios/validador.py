"""Validaciones de negocio para el sistema de gestión de gastos.

Este módulo contiene las validaciones necesarias para asegurar la integridad
de los datos antes de guardarlos en la base de datos o procesarlos."""

import re
from typing import Optional


class Validador:
    """Validador de datos de transacciones y notificaciones."""

    @staticmethod
    def validar_monto(monto: float) -> bool:
        """Valida que el monto sea un número positivo."""
        return isinstance(monto, (int, float)) and monto > 0

    @staticmethod
    def validar_tipo(tipo: str) -> bool:
        """Valida que el tipo sea 'ingreso' o 'gasto'."""
        return tipo in ("ingreso", "gasto")

    @staticmethod
    def validar_destinatario(destinatario: str) -> bool:
        """Valida que el destinatario no esté vacío y tenga formato adecuado."""
        return bool(destinatario) and len(destinatario.strip()) >= 2

    @staticmethod
    def validar_formato_monto(monto_str: str) -> bool:
        """Valida que el string del monto tenga un formato numérico adecuado."""
        # Patrones: "1.00", "1", "1,50", "S/ 1.00"
        patrones = [r"^\d+(\.\d{1,2})?$", r"^\d+,\d{1,2}$", r"^S/\s*\d+(\.\d{1,2})?$"]
        return any(re.match(patron, monto_str) for patron in patrones)

    @staticmethod
    def sanitizar_texto(texto: str) -> str:
        """Sanitiza texto removiendo caracteres peligrosos y normalizando espacios."""
        if not texto:
            return ""
        # Remover caracteres de control y múltiples espacios
        texto_limpio = re.sub(r"\s+", " ", texto.strip())
        # Remover caracteres no imprimibles
        texto_limpio = re.sub(r"[^\x20-\x7EáéíóúÁÉÍÓÚñÑ]", "", texto_limpio)
        return texto_limpio
