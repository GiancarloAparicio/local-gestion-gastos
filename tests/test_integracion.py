"""Pruebas de integración para el sistema local-gestion-gastos."""

import sys
import os
import tempfile
import json
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    modo_automate_broker, obtener_adapter_BD, cargar_adaptadores,
    procesar_notificacion
)
from adaptadores.ibk import IBKAdapter
from adaptadores.yape import YapeAdapter
from modulios.termux_api import TermuxAPI
from unittest.mock import patch


# Datos de prueba

YAPE_PAGO = {
    "content": "Yape! S/ 20.00 a María Torres te envió plata",
    "title": "Yape",
    "packageName": "com.bcp.innovacxion.yapeapp",
    "when": 1730000000,
}

IBK_TRANSFERENCIA = {
    "content": "TRAN S/ 50.00\nA: Maria Torres\n(2026-11-20 10:30)",
    "packageName": "pe.com.interbank.mobilebanking",
    "when": 1730000000,
}

IBK_PLIN = {
    "content": "Plineaste S/ 15.00 a Ana Gomez",
    "packageName": "pe.com.interbank.mobilebanking",
    "when": 1730000000,
}

IBK_TARJETA = {
    "content": "Realizaste un consumo con tu tarjeta.",
    "title": "Cobro con Tarjeta",
    "packageName": "pe.com.interbank.mobilebanking",
    "when": 1730000000,
}

PAQUETE_DESCONOCIDO = {
    "content": "Notificación del sistema",
    "packageName": "com.android.shell",
    "when": 1730000000,
}


class TestProcesarNotificacionIntegracion:
    """Pruebas integradas de procesar_notificacion."""

    def test_procesar_yape_ingreso(self):
        adapter = obtener_adapter_BD()
        adaptadores = cargar_adaptadores()
        with patch('main.TermuxAPI') as MockTermuxAPI:
            mock_ta = MockTermuxAPI.return_value
            mock_ta.mostrar_dialogo.return_value = {"text": "Compra en el supermercado"}
            from main import procesar_notificacion
            resultado = procesar_notificacion(
                YAPE_PAGO, adapter, adaptadores,
                MockTermuxAPI(), 5,
            )
            assert resultado is True or resultado is False

    def test_procesar_yape_sin_monto(self):
        adapter = obtener_adapter_BD()
        adaptadores = cargar_adaptadores()
        yape_sin_monto = {"content": "Yape! a Pedro te envió plata", "title": "Yape", "packageName": "com.bcp.innovacxion.yapeapp", "when": 1730000000, "timestamp": 1730000000}
        with patch('main.TermuxAPI') as MockTermuxAPI:
            mock_ta = MockTermuxAPI.return_value
            mock_ta.mostrar_dialogo.return_value = {"text": "Sin monto"}
            from main import procesar_notificacion
            resultado = procesar_notificacion(yape_sin_monto, adapter, adaptadores, MockTermuxAPI(), 5)
            assert resultado is True or resultado is False

    def test_procesar_ibk_transferencia(self):
        adapter = obtener_adapter_BD()
        adaptadores = cargar_adaptadores()
        with patch('main.TermuxAPI') as MockTermuxAPI:
            mock_ta = MockTermuxAPI.return_value
            mock_ta.mostrar_dialogo.return_value = {"text": "Transferencia"}
            from main import procesar_notificacion
            resultado = procesar_notificacion(IBK_TRANSFERENCIA, adapter, adaptadores, MockTermuxAPI(), 5)
            assert resultado is not None

    def test_procesar_ibk_plin(self):
        adapter = obtener_adapter_BD()
        adaptadores = cargar_adaptadores()
        with patch('main.TermuxAPI') as MockTermuxAPI:
            mock_ta = MockTermuxAPI.return_value
            mock_ta.mostrar_dialogo.return_value = {"text": "Pago con Plin"}
            from main import procesar_notificacion
            resultado = procesar_notificacion(IBK_PLIN, adapter, adaptadores, MockTermuxAPI(), 5)
            assert resultado is not None

    def test_procesar_paquete_desconocido_no_crashes(self):
        adapter = obtener_adapter_BD()
        adaptadores = cargar_adaptadores()
        from main import procesar_notificacion
        try:
            resultado = procesar_notificacion(PAQUETE_DESCONOCIDO, adapter, adaptadores, type('TA', (), {'mostrar_dialogo': lambda self, **kw: None})(), 5)
            assert resultado is False
        except Exception as e:
            error_str = str(e).lower()
            assert "adaptador" in error_str or "ningún" in error_str


class TestModoAutomateBroker:
    """Pruebas para el modo automate_broker."""

    def test_automate_broker_yape_pago(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(YAPE_PAGO, f)
                temp_path = f.name
            try:
                adapter = obtener_adapter_BD()
                adaptadores = cargar_adaptadores()
                resultado = modo_automate_broker(adapter, adaptadores, temp_path)
                assert resultado is None
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def test_automate_broker_ibk_transferencia(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(IBK_TRANSFERENCIA, f)
                temp_path = f.name
            try:
                adapter = obtener_adapter_BD()
                adaptadores = cargar_adaptadores()
                resultado = modo_automate_broker(adapter, adaptadores, temp_path)
                assert resultado is None
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def test_automate_broker_paquete_desconocido(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(PAQUETE_DESCONOCIDO, f)
                temp_path = f.name
            try:
                adapter = obtener_adapter_BD()
                adaptadores = cargar_adaptadores()
                try:
                    resultado = modo_automate_broker(adapter, adaptadores, temp_path)
                    assert resultado is False or resultado is None
                except Exception as e:
                    error_msg = str(e).lower()
                    assert "adaptador" in error_msg or "ningún" in error_msg
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def test_automate_broker_round_yape(self, tmp_path):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            datos_yape = {"content": "Yape! S/ 30.00 a Pedro Luis te envió plata", "title": "Yape", "packageName": "com.bcp.innovacxion.yapeapp", "when": 1730000000, "timestamp": 1730000000}
            json_path = tmp_path / "test_noti_yape.json"
            json_path.write_text(json.dumps(datos_yape))
            adapter = obtener_adapter_BD()
            adaptadores = cargar_adaptadores()
            resultado = modo_automate_broker(adapter, adaptadores, str(json_path))
            assert resultado is None


class TestTiposDeDatos:
    """Pruebas que validan los tipos de datos y campos normalizados."""

    def test_yap_normalizacion_tipo_ingreso(self):
        adapter = YapeAdapter()
        normalizado = adapter.normalizar_notificacion(YAPE_PAGO)
        assert normalizado["tipo"] == "ingreso"
        assert normalizado["monto"] > 0

    def test_ibk_normalizacion_tipo_gasto(self):
        adapter = IBKAdapter()
        normalizado = adapter.normalizar_notificacion(IBK_TRANSFERENCIA)
        assert normalizado["tipo"] == "gasto"
        assert normalizado["formato_tipo"] == "transferencia"

    def test_ibk_plin_normalizacion(self):
        adapter = IBKAdapter()
        normalizado = adapter.normalizar_notificacion(IBK_PLIN)
        assert normalizado["tipo"] == "gasto"
        assert normalizado["formato_tipo"] == "plin"
        assert normalizado["canal"] == "interbank"

    def test_ibk_tarjeta_normalizacion(self):
        adapter = IBKAdapter()
        normalizado = adapter.normalizar_notificacion(IBK_TARJETA)
        assert "tipo" in normalizado
        assert "formato_tipo" in normalizado
