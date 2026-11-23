from main import MAPEO_ADAPTADORES
"""Pruebas para los adaptadores del sistema."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adaptadores.ibk import IBKAdapter
from adaptadores.yape import YapeAdapter
from main import encontrar_adaptador, cargar_adaptadores


def test_encontrar_adaptador_yape():
    """Paquete Yape debe hacer match con adaptador yape."""
    adaptadores = {"yape": YapeAdapter}
    resultado = encontrar_adaptador("com.bcp.innovacxion.yapeapp", adaptadores)
    assert resultado is not None
    assert isinstance(resultado, YapeAdapter)


def test_encontrar_adaptador_ibk():
    """Paquete IBK debe hacer match con adaptador ibk."""
    adaptadores = {"ibk": IBKAdapter}
    resultado = encontrar_adaptador("pe.com.interbank.mobilebanking", adaptadores)
    assert resultado is not None
    assert isinstance(resultado, IBKAdapter)


def test_encontrar_adaptador_desconocido():
    """Paquete desconocido debe retornar None."""
    adaptadores = {"yape": YapeAdapter, "ibk": IBKAdapter}
    resultado = encontrar_adaptador("com.android.shell", adaptadores)
    assert resultado is None


def test_cargar_adaptadores():
    """Probar carga de adaptadores desde config."""
    adaptadores = cargar_adaptadores()
    # Debería cargar los adaptadores activos desde config.yaml
    assert adaptadores is not None
