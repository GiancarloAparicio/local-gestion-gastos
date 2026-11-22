"""Interfaz común (ABC) para todos los adaptadores de banco.

Todas las clases adaptador deben heredar de esta base e implementar los métodos
abstractos. Esto permite que la lógica de dominio permanezca independiente de
cualquier banco o formato de notificación en particular."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BancoAdapter(ABC):
    """Clase base abstracta para adaptadores de notificaciones bancarias."""

    @abstractmethod
    def es_mis_notificacion(self, datos_crudos: Dict[str, Any]) -> bool:
        """Determina si estos datos crudos corresponden a este banco.

        Args:
            datos_crudos: Diccionario con los datos de la notificación tal como
            llegaron (formato Termux o Automate). El adaptador debe inspeccionar
            el campo 'paquete' (Termux) o 'package' (Automate) para decidir.

        Returns:
            True si la notificación es de este banco, False en caso contrario.
        """
        pass

    @abstractmethod
    def normalizar_notificacion(self, datos_crudos: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte datos crudos a diccionario normalizado estándar.

        Este es el método core de cada adaptador. Debe extraer los siguientes
        campos obligatorios del mensaje del banco y retornar un diccionario con
        estructura consistente para el resto del sistema.

        Campos obligatorios en el diccionario resultado:
        - monto: float (siempre > 0)
        - tipo: "ingreso" o "gasto"
        - destinatario: str (persona o comercio)
        - event_id: str (UUID único o tomado del key/notification_id)
        - canal: str ("yape", "plin", "bbva", "interbank", "nfc", "manual")
        - fecha_hora: str (formato ISO 8601)
        - mensaje_raw: str (el texto tal y como llegó, sin modificar)
        - motivo: None (siempre - se solicitará al usuario después)
        - fuente: "termux" o "automate"

        Args:
            datos_crudos: Diccionario con los datos crudos de la notificación.

        Returns:
            Diccionario con campos normalizados listo para ser insertado en SQLite.
        """
        pass
