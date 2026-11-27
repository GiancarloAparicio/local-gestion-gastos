"""Proveedor de notificaciones bancarias multiplataforma.

- Termux: lee ``termux-notification-list`` (JSON) y filtra paquetes de bancos.
- Linux: no hay notificaciones Android; retorna un error controlado para que el
  llamador use el modo broker (archivos) o el registro manual.

Sobre JSON estándar:
    {"code": 0|-1, "data": {...}, "raw": "...", "valid": bool, "error": str|None}
"""

from abc import ABC, abstractmethod
import json
import os
import re
import subprocess
import time
from datetime import datetime

from infraestructura import config


def _sobre(code, data=None, raw="", error=None):
    return {
        "code": code,
        "data": data if data is not None else {},
        "raw": raw,
        "valid": code == 0,
        "error": error,
    }


# Paquetes conocidos -> canal lógico
PAQUETES_CANAL = {
    "pe.com.interbank.mobilebanking": "interbank",
    "com.bcp.innovacxion.yapeapp": "yape",
    "com.google.android.apps.walletnfcrel": "nfc",
    "pe.com.compartamos.bancamovil": "compartamos",
    "manual.entry": "manual",
}


def _extraer_monto(mensaje: str):
    m = re.search(r"S/\s*([\d.,]+)", mensaje or "")
    if not m:
        return None
    valor = m.group(1)
    # Formato peruano: punto decimal cuando hay 2 dígitos finales
    try:
        if re.search(r"[.,]\d{2}$", valor):
            valor = valor.replace(",", ".")
        else:
            valor = valor.replace(",", "").replace(".", "")
        return float(valor)
    except (TypeError, ValueError):
        return None


def _determinar_tipo(mensaje: str) -> str:
    m = (mensaje or "").lower()
    if any(p in m for p in ("te envió", "te ha plineado", "te abonó", "recibiste")):
        return "ingreso"
    if any(p in m for p in ("plineaste", "consumo", "gastaste", "pago con", "debit")):
        return "gasto"
    return "indeterminado"


def _extraer_destinatario(mensaje: str) -> str:
    m = re.search(r"\ba\s+([A-ZÁÉÍÓÚÑ][\wÑ\.\s]{2,40})", mensaje or "")
    if m:
        return m.group(1).strip().rstrip(".!,;:")
    return "desconocido"


class NotificationProvider(ABC):
    """Contrato de captura de notificaciones."""

    @abstractmethod
    def capturar_notificacion(self) -> dict:
        """Captura la notificación más reciente relevante."""

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        paquete = (
            datos_crudos.get("packageName")
            or datos_crudos.get("package")
            or datos_crudos.get("paquete", "")
        )
        return paquete in PAQUETES_CANAL

    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        mensaje = datos_crudos.get("content") or datos_crudos.get("message", "")
        paquete = (
            datos_crudos.get("packageName")
            or datos_crudos.get("package")
            or datos_crudos.get("paquete", "")
        )
        when = datos_crudos.get("when") or datos_crudos.get("timestamp")
        try:
            timestamp = float(when)
        except (TypeError, ValueError):
            try:
                timestamp = datetime.fromisoformat(str(when)).timestamp()
            except (TypeError, ValueError):
                timestamp = time.time()
        return {
            "paquete": paquete,
            "app": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "titulo": datos_crudos.get("title", datos_crudos.get("titulo", "")),
            "mensaje": mensaje,
            "monto": _extraer_monto(mensaje),
            "tipo": _determinar_tipo(mensaje),
            "destinatario": _extraer_destinatario(mensaje),
            "event_id": str(
                datos_crudos.get("key")
                or datos_crudos.get("notification_id")
                or datos_crudos.get("id")
                or timestamp
            ),
            "timestamp": timestamp,
            "canal": PAQUETES_CANAL.get(paquete, "desconocido"),
            "motivo": None,
            "mensaje_raw": mensaje,
        }


class TermuxNotificationProvider(NotificationProvider):
    """Captura notificaciones nativas vía ``termux-notification-list``."""

    def _bin(self, nombre: str) -> str:
        return os.path.join(config.termux_bin(), nombre)

    def _leer_notificaciones(self) -> list:
        try:
            resultado = subprocess.run(
                [self._bin("termux-notification-list")],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            return []
        except subprocess.TimeoutExpired:
            return []
        except Exception:
            return []

        salida = (resultado.stdout or "").strip()
        if not salida:
            return []
        try:
            datos = json.loads(salida)
            return datos if isinstance(datos, list) else [datos]
        except json.JSONDecodeError:
            return []

    def capturar_notificacion(self) -> dict:
        notificaciones = self._leer_notificaciones()
        relevantes = [n for n in notificaciones if self.es_mis_notificacion(n)]
        if not relevantes:
            return _sobre(-1, raw="sin notificaciones relevantes", error="sin_notificaciones")
        # Ordenar por 'when' si está disponible (más reciente primero)
        try:
            relevantes.sort(key=lambda n: str(n.get("when", "")), reverse=True)
        except Exception:
            pass
        elegida = relevantes[0]
        normalizado = self.normalizar_notificacion(elegida)
        return _sobre(
            0,
            normalizado,
            raw=json.dumps(elegida, ensure_ascii=False),
        )


class LinuxNotificationProvider(NotificationProvider):
    """Linux no expone notificaciones Android: error controlado."""

    def capturar_notificacion(self) -> dict:
        return _sobre(
            -1,
            raw="linux: use modo broker o registro manual",
            error="notificaciones_no_disponibles_en_linux",
        )
