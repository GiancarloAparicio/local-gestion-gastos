"""Módulo de entrada de datos al usuario.
Proveedor abstracto y ambas implementaciones (Termux/Linux) que siempre
retornan el mismo formato JSON estandarizado:
{"code": 0|-1, "text": "", "raw": "", "valid": true|false, "error": null|str}
"""

from abc import ABC, abstractmethod


class InputProvider(ABC):
    """Interfaz unificada para entrada de datos al usuario."""
    
    @abstractmethod
    def solicitar_texto(self, pregunta: str, timeout: int = 30) -> dict:
        """Solicita texto al usuario. Retorna dict JSON estandarizado."""
        pass
    
    @abstractmethod
    def solicitar_numero(self, pregunta: str, min_val: float = None, max_val: float = None) -> dict:
        """Solicita número al usuario. Retorna dict JSON estandarizado."""
        pass
    
    @abstractmethod
    def solicitar_confirmacion(self, pregunta: str) -> dict:
        """Solicita confirmación S/N. Retorna dict JSON estandarizado."""
        pass