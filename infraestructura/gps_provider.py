"""Módulo de proveedor de ubicación GPS.
Proporciona una interfaz unificada para obtener ubicación en Termux y Linux,
siempre retornando el mismo formato JSON estandarizado:
{"code": 0|-1, "data": {"lat": float, "lng": float, "altitud": float|None, "precision": float, "source": str, "timestamp": float}, "raw": "", "valid": true|false, "error": null|str}
"""

from abc import ABC, abstractmethod
import subprocess
import time
import json
import sqlite3
import os


class GPSProvider(ABC):
    """Provedor abstracto de ubicación GPS."""
    
    @abstractmethod
    def obtener_ubicacion(self) -> dict:
        """Retorna ubicación actual. Siempre JSON estandarizado."""
        pass
    
    @abstractmethod
    def ultimo_conocido(self) -> dict:
        """Retorna última ubicación guardada en historial."""
        pass


class TermuxGPSProvider(GPSProvider):
    """Implementación para Termux usando termux-location"""
    
    def _ejecutar_termux_location(self, timeout: int = 15) -> dict:
        """Ejecuta termux-location y parsea output a JSON estandarizado"""
        try:
            result = subprocess.run(
                ["termux-location", "gps"],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout.strip()
            
            parsed = self._parsear_output(output)
            
            # Siempre retornar estructura consistente: code en raíz, data dentro
            return {
                "code": 0 if parsed else -1,
                "data": parsed if parsed else {},
                "raw": output,
                "valid": parsed is not None,
                "error": None if parsed else "fallo_parsing_termux_location"
            }
        except subprocess.TimeoutExpired:
            return {
                "code": -1,
                "data": {},
                "raw": "",
                "valid": False,
                "error": "timeout_expirado_termux_location"
            }
        except Exception as e:
            return {
                "code": -1,
                "data": {},
                "raw": str(e),
                "valid": False,
                "error": str(e)
            }
    
    def _parsear_output(self, output: str) -> dict | None:
        """Parsea output de termux-location a dict estandarizado"""
        try:
            # Intentar JSON primero
            if output.startswith("{"):
                data = json.loads(output)
                return {
                    "lat": float(data.get("latitude", data.get("lat", 0))),
                    "lng": float(data.get("longitude", data.get("lng", 0))),
                    "altitud": float(data.get("altitud", data.get("altitude"))) if (
                        data.get("altitud") or data.get("altitude")
                    ) else None,
                    "precision": float(data.get("accuracy", data.get("precision", 0))),
                    "source": "termux-location",
                    "timestamp": float(data.get("timestamp", time.time()))
                }
            
            # Parsear valores separados por línea (termux-location a veces output así)
            lines = [l.strip() for l in output.split("\n") if l.strip()]
            if len(lines) >= 2:
                try:
                    return {
                        "lat": float(lines[0]),
                        "lng": float(lines[1]),
                        "altitud": float(lines[2]) if len(lines) > 2 else None,
                        "precision": float(lines[3]) if len(lines) > 3 else None,
                        "source": "termux-location",
                        "timestamp": time.time()
                    }
                except (ValueError, IndexError):
                    pass
            
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            pass
        
        return None
    
    def obtener_ubicacion(self) -> dict:
        """Obtener ubicación actual en tiempo real via termux-location"""
        return self._ejecutar_termux_location(timeout=10)
    
    def ultimo_conocido(self) -> dict:
        """Obtener última ubicación de SQLite o archivo de caché en Termux"""
        # En Termux, leeríamos de la tabla de historial de GPS en SQLite
        # Por ahora retornar estructura indicando que requiere BD
        return {
            "code": -1,
            "data": {},
            "raw": "ultimo_conocido_requiere_consulta_sqlite",
            "valid": False,
            "error": "ultimo_conocido_requiere_base_datos"
        }


class LinuxGPSProvider(GPSProvider):
    """Implementación para Linux standard usando Python y geolocalización por IP"""
    
    def _obtener_por_ip_geolocation(self) -> dict | None:
        """Obtener ubicación por IP usando ipapi.co o similar"""
        try:
            import urllib.request
            url = "https://ipapi.co/json/"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return {
                    "lat": float(data.get("latitude", 0)),
                    "lng": float(data.get("longitude", 0)),
                    "altitud": None,  # IP geolocation no da altitud
                    "precision": float(data.get("accuracy", 0)),
                    "source": "ip-api",
                    "timestamp": time.time()
                }
        except ImportError:
            pass
        except Exception as e:
            # Si falla, continuar con método alternativo
            pass
        return None
    
    def _obtener_ultimo_conocido_sqlite(self) -> dict | None:
        """Obtener última ubicación de SQLite en Linux"""
        db_path = os.path.expanduser("~/local_gastos.db")
        try:
            conexion = sqlite3.connect(db_path)
            cursor = conexion.cursor()
            
            # Intentar leer última ubicación de la tabla de transacciones
            try:
                cursor.execute(
                    "SELECT latitud, longitud, fecha_hora_epoch FROM transacciones "
                    "WHERE latitud IS NOT NULL AND longitud IS NOT NULL "
                    "ORDER BY fecha_hora_epoch DESC LIMIT 1"
                )
                fila = cursor.fetchone()
                if fila:
                    return {
                        "lat": float(fila[0]),
                        "lng": float(fila[1]),
                        "altitud": None,
                        "precision": None,
                        "source": "sqlite-history",
                        "timestamp": float(fila[2]) if fila[2] else time.time()
                    }
            except sqlite3.OperationalError:
                pass  # Tabla puede no existir aún
            
            conexion.close()
        except Exception:
            pass
        
        return None
    
    def obtener_ubicacion(self) -> dict:
        """Obtener ubicación actual en Linux"""
        # Primero intentar IP geolocation
        resultado = self._obtener_por_ip_geolocation()
        if resultado:
            # Estructurar consistentemente con code en raíz y data
            return {
                "code": 0,
                "data": resultado,
                "raw": "ip_geolocation_success",
                "valid": True,
                "error": None
            }
        
        # Fallback: último conocido de SQLite
        resultado_sqlite = self._obtener_ultimo_conocido_sqlite()
        if resultado_sqlite:
            return {
                "code": 0,
                "data": resultado_sqlite,
                "raw": "from_sqlite_history",
                "valid": True,
                "error": None
            }
        
        # Sin GPS disponible - estructura consistente
        return {
            "code": -1,
            "data": {},
            "raw": "no_hay_gps_hardware_en_pc_ni_datos_sqlite",
            "valid": False,
            "error": "gps_no_disponible_en_este_equipo"
        }
    
    def ultimo_conocido(self) -> dict:
        """Última ubicación guardada en SQLite en Linux"""
        db_path = os.path.expanduser("~/local_gastos.db")
        try:
            conexion = sqlite3.connect(db_path)
            cursor = conexion.cursor()
            
            try:
                cursor.execute(
                    "SELECT latitud, longitud, fecha_hora_epoch FROM transacciones "
                    "WHERE latitud IS NOT NULL AND longitud IS NOT NULL "
                    "ORDER BY fecha_hora_epoch DESC LIMIT 1"
                )
                fila = cursor.fetchone()
                if fila:
                    conexion.close()
                    return {
                        "code": 0,
                        "data": {
                            "lat": float(fila[0]),
                            "lng": float(fila[1]),
                            "altitud": None,
                            "precision": None,
                            "source": "sqlite-history",
                            "timestamp": float(fila[2]) if fila[2] else time.time()
                        },
                        "raw": "from_sqlite_history",
                        "valid": True,
                        "error": None
                    }
            except sqlite3.OperationalError:
                pass
            
            conexion.close()
        except Exception:
            pass
        
        return {
            "code": -1,
            "data": {},
            "raw": "no_hay_datos_en_sqlite",
            "valid": False,
            "error": "no_hay_ubicaciones_guardadas"
        }