"""Pruebas unitarias para el módulo consolidador."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from modulios.consolidador import Consolidador


class TestConsolidadorVentana:
    """Pruebas para la ventana de consolidación."""

    def test_ventana_5min_por_defecto(self):
        """Probar que la ventana por defecto es de 5 minutos."""
        c = Consolidador(ventana_minutos=5)
        assert c.ventana_minutos == 5

    def test_debe_consolidar_dentro_de_ventana(self):
        """Probar que las notificaciones dentro de 5 minutos se consolidan."""
        c = Consolidador(ventana_minutos=5)
        ahora = datetime.now()
        dentro_de_ventana = ahora - timedelta(minutes=3)

        assert c.debe_consolidar(ahora, dentro_de_ventana) is True

    def test_no_consolidar_fuera_de_ventana(self):
        """Probar que las notificaciones fuera de 5 minutos no se consolidan."""
        c = Consolidador(ventana_minutos=5)
        ahora = datetime.now()
        fuera_de_ventana = ahora - timedelta(minutes=10)

        assert c.debe_consolidar(ahora, fuera_de_ventana) is False

    def test_consolidador_ventana_corta(self):
        """Probar con ventana de 2 minutos."""
        c = Consolidador(ventana_minutos=2)
        ahora = datetime.now()
        dentro = ahora - timedelta(minutes=1)
        fuera = ahora - timedelta(minutes=5)

        assert c.debe_consolidar(ahora, dentro) is True
        assert c.debe_consolidar(ahora, fuera) is False
