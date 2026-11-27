"""Proveedor de ubicación GPS multiplataforma.

- Termux: usa ``termux-location`` (ruta tomada de ``config.termux.path``).
- Linux: usa geolocalización por IP (ipapi.co / ipinfo.io) como aproximación.

Ambos retornan el mismo sobre JSON estándar:
    {"code": 0|-1, "data": {"lat": float, "lng": float, "altitud": float|None,
     "precision": float|None, "source": str, "timestamp": float},
     "raw": "...", "valid": bool, "error": str|None}
"""

from abc import ABC, abstractmethod
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

from infraestructura import config


def _sobre(code, data=None, raw="", error=None):
    return {
        "code": code,
        "data": data if data is not None else {},
        "raw": raw,
        "valid": code == 0,
        "error": error,
    }


class GPSProvider(ABC):
    """Contrato de proveedor GPS."""

    @abstractmethod
    def obtener_ubicacion(self) -> dict:
        """Ubicación actual (o fallback). Sobre JSON estándar."""

    @abstractmethod
    def ultimo_conocido(self) -> dict:
        """Última ubicación registrada en la base de datos."""


def _ultima_ubicacion_db() -> dict | None:
    """Lee la última ubicación válida desde la BD configurada."""
    import sqlite3

    try:
        conexion = sqlite3.connect(config.ruta_db())
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT latitud, longitud, fuente_gps, fecha_hora_epoch "
            "FROM transacciones WHERE latitud IS NOT NULL AND longitud IS NOT NULL "
            "ORDER BY fecha_hora_epoch DESC LIMIT 1"
        )
        fila = cursor.fetchone()
        conexion.close()
        if fila:
            return {
                "lat": float(fila["latitud"]),
                "lng": float(fila["longitud"]),
                "altitud": None,
                "precision": None,
                "source": "sqlite-history",
                "timestamp": float(fila["fecha_hora_epoch"] or time.time()),
            }
    except Exception:
        pass
    return None


class TermuxGPSProvider(GPSProvider):
    """GPS real vía ``termux-location`` dentro de Termux."""

    def _bin(self, nombre: str) -> str:
        return os.path.join(config.termux_bin(), nombre)

    def obtener_ubicacion(self) -> dict:
        timeout = config.timeout_gps()
        cmd = self._bin("termux-location")
        try:
            resultado = subprocess.run(
                [cmd, "-p", "gps", "-r", "once"],
                capture_output=True,
                text=True,
                timeout=timeout + 5,
            )
            salida = (resultado.stdout or "").strip()
            if resultado.returncode == 0 and salida:
                try:
                    datos = json.loads(salida)
                    lat = datos.get("latitude", datos.get("lat"))
                    lng = datos.get("longitude", datos.get("lon"))
                    if lat is not None and lng is not None:
                        return _sobre(
                            0,
                            {
                                "lat": float(lat),
                                "lng": float(lng),
                                "altitud": datos.get("altitude"),
                                "precision": datos.get("accuracy"),
                                "source": "termux-location",
                                "timestamp": time.time(),
                            },
                            raw=salida,
                        )
                except (json.JSONDecodeError, ValueError):
                    pass
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

        # Fallback: última ubicación de la BD
        ultimo = _ultima_ubicacion_db()
        if ultimo:
            return _sobre(0, ultimo, raw="fallback BD")
        return _sobre(-1, raw="termux-location no disponible", error="gps_no_disponible")

    def ultimo_conocido(self) -> dict:
        ultimo = _ultima_ubicacion_db()
        if ultimo:
            return _sobre(0, ultimo, raw="última ubicación BD")
        return _sobre(-1, raw="sin ubicaciones", error="sin_ubicaciones")


class LinuxGPSProvider(GPSProvider):
    """GPS aproximado por IP para equipos Linux sin hardware GPS."""

    _SERVICIOS = (
        "https://ipapi.co/json/",
        "https://ipinfo.io/json",
    )

    def _por_ip(self) -> dict | None:
        for url in self._SERVICIOS:
            try:
                with urllib.request.urlopen(url, timeout=10) as respuesta:
                    datos = json.loads(respuesta.read().decode("utf-8"))
                # ipinfo devuelve 'loc' = "lat,lng"
                if "loc" in datos and "," in str(datos["loc"]):
                    lat_s, lng_s = str(datos["loc"]).split(",", 1)
                    lat, lng = float(lat_s), float(lng_s)
                else:
                    lat = float(datos.get("latitude", datos.get("lat", 0)))
                    lng = float(datos.get("longitude", datos.get("lng", 0)))
                if lat or lng:
                    return {
                        "lat": lat,
                        "lng": lng,
                        "altitud": None,
                        "precision": datos.get("accuracy"),
                        "source": "ip-geolocation",
                        "timestamp": time.time(),
                    }
            except (urllib.error.URLError, urllib.error.HTTPError):
                continue
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                continue
        return None

    def obtener_ubicacion(self) -> dict:
        ubicacion = self._por_ip()
        if ubicacion:
            return _sobre(0, ubicacion, raw="geolocalización por IP")
        ultimo = _ultima_ubicacion_db()
        if ultimo:
            return _sobre(0, ultimo, raw="fallback BD")
        return _sobre(
            -1,
            raw="sin GPS ni ubicaciones previas",
            error="gps_no_disponible",
        )

    def ultimo_conocido(self) -> dict:
        ultimo = _ultima_ubicacion_db()
        if ultimo:
            return _sobre(0, ultimo, raw="última ubicación BD")
        return _sobre(-1, raw="sin ubicaciones", error="sin_ubicaciones")
