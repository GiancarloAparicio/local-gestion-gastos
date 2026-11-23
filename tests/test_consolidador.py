"""Pruebas para el consolidador."""

from main import Consolidador
from datetime import datetime, timedelta


def test_ventana_5min():
    """Probar ventana de consolidación de 5 minutos."""
    c = Consolidador(ventana_minutos=5)
    ahora = datetime.now()
    dentro = ahora - timedelta(minutes=3)
    fuera = ahora - timedelta(minutes=10)
    
    assert c.debe_consolidar(ahora, dentro) is True
    assert c.debe_consolidar(ahora, fuera) is False


def test_ventana_corta():
    """Probar con ventana de 2 minutos."""
    c = Consolidador(ventana_minutos=2)
    ahora = datetime.now()
    dentro = ahora - timedelta(minutes=1)
    fuera = ahora - timedelta(minutes=5)
    
    assert c.debe_consolidar(ahora, dentro) is True
    assert c.debe_consolidar(ahora, fuera) is False
