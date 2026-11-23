"""Módulo Termux API - Conexión con los comandos nativos de Termux.

Proporciona funciones seguras para invocar:
- termux-notification-list - Listar notificaciones entrantes
- termux-dialog - Mostrar diálogos al usuario
- termux-location - Obtener ubicación GPS
- termux-notification-remove - Remover notificaciones procesadas
"""

import os
import subprocess
import logging
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("TermuxAPI")

# --- Configuración única de Termux (única fuente de verdad) ---
# Ruta donde residen los binarios de Termux (se sobreescribe desde main.py usando config.yaml)
TERMUX_PATH = "/data/data/com.termux/files/usr/bin"

# Diccionario de comandos - definición única, usada por la clase
COMMANDS = {
    "notification_list": "termux-notification-list",
    "dialog": "termux-dialog",
    "location": "termux-location",
    "notification_remove": "termux-notification-remove",
}


class TermuxAPI:
    """Clase que encapsula los comandos de Termux API."""

    def __init__(self, termux_path=None):
        # Usar la ruta proporcionada o la por defecto del módulo
        self.termux_path = termux_path or TERMUX_PATH
        # Disponibilidad se establece como None (pending) y se verifica bajo demanda
        self._available_commands = None

    def _get_command_path(self, cmd_name):
        """Obtiene la ruta completa de un comando de Termux usando self.termux_path."""
        cmd_name_val = self.COMMANDS.get(cmd_name)
        if not cmd_name_val:
            return None
        return os.path.join(self.termux_path, cmd_name_val)

    def _check_available_commands(self):
        """Verifica qué comandos de Termux están disponibles en el sistema.

        Intenta ejecutar cada comando con --version. Si falla por FileNotFoundError,
        el comando no está en la ruta configurada (expected en Linux, normal en Termux).
        Si el comando se ejecuta (retorno 0), está disponible.

        Returns dict con {nombre: bool} - solo se llama bajo demanda.
        """
        available = {}
        for name, cmd in self.COMMANDS.items():
            try:
                cmd_path = self._get_command_path(name)
                if cmd_path:
                    result = subprocess.run(
                        [cmd_path, "--version"], capture_output=True, text=True, timeout=5
                    )
                    available[name] = result.returncode == 0
                else:
                    available[name] = False
            except FileNotFoundError:
                # Binario no existe en esta ruta (expected en Linux, normal en Termux)
                # No logar warning aquí - se logará cuando se intente usar el comando
                available[name] = False
            except (subprocess.TimeoutExpired, OSError):
                available[name] = False
            except Exception:
                available[name] = False
        return available

    def _verificar_comando_en_ruta(self, cmd_name):
        """Verifica si un comando específico está disponible en la ruta actual.

        Usado bajo demanda antes de ejecutar un comando.
        Retorna True si el comando existe y es ejecutable, False si no.
        """
        try:
            cmd_path = self._get_command_path(cmd_name)
            if not cmd_path:
                return False
            result = subprocess.run(
                [cmd_path, "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except FileNotFoundError:
            # Binario no encontrado en esta ruta
            return False
        except Exception:
            return False

    def mostrar_dialogo(self, widget: str = "text", titulo: str = None,
                        mensaje: str = "", **kwargs) -> Optional[Dict]:
        """Muestra un diálogo usando termux-dialog.

        Verifica disponibilidad bajo demanda. Si el comando no existe,
        retorna None y el llamador decidirá qué hacer.
        """
        # Verificar disponibilidad bajo demanda (solo la primera vez)
        if self._available_commands is None:
            self._available_commands = self._check_available_commands()

        if not self._available_commands.get("dialog", False):
            # Comando no disponible en esta ruta - retornar None gracefully
            # No logar warning aquí para evitar spurious messages
            return None

        args = [widget]
        if titulo:
            args.extend(["-t", titulo])
        if mensaje:
            args.extend(["-i", mensaje])

        # Agregar argumentos adicionales
        for key, value in kwargs.items():
            if value is not None:
                arg_name = f"-{key[0]}" if len(key) == 1 else f"--{key[0]}"
                args.append(f"{arg_name} {value}")

        output = self._ejecutar_comando(self.COMMANDS["dialog"], args)
        if not output:
            return None

        try:
            import json
            resultado = json.loads(output)
            return resultado
        except json.JSONDecodeError:
            return {"raw": output}

    def _ejecutar_comando(self, comando_nombre: str, args: List[str] = None) -> Optional[str]:
        """Ejecuta un comando de Termux de manera segura."""
        try:
            cmd_path = self._get_command_path(comando_nombre)
            if not cmd_path:
                # Comando no definido en COMMANDS
                return None

            full_cmd = [cmd_path]
            if args:
                full_cmd.extend(args)

            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                return result.stdout.strip() if result.stdout else None
            else:
                # Comando existió pero falló - esto es informativo
                # pero no levantamos excepción ni spurious warnings al init
                return None
        except FileNotFoundError:
            # Binario no existe en esta ruta (expected en Linux, normal en Termux)
            return None
        except Exception as e:
            # Error genérico - logar pero no hacer crashear
            logger.debug(f"Excepción ejecutando comando Termux: {e}")
            return None

    def obtener_gps(self, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """Obtiene ubicación GPS con fallback a base de datos."""
        import json
        import sqlite3

        # 1. Intentar GPS en tiempo real
        try:
            cmd_path = self._get_command_path("location")
            if cmd_path:
                result = subprocess.run(
                    [cmd_path, "-g", str(timeout)],
                    capture_output=True, text=True, timeout=timeout + 5
                )

                if result.returncode == 0 and result.stdout.strip():
                    data = json.loads(result.stdout.strip())
                    lat = data.get('latitude')
                    lng = data.get('longitude')

                    if lat is not None and lng is not None:
                        return {
                            'latitud': float(lat),
                            'longitud': float(lng),
                            'fuente_gps': 'live'
                        }
            # Si no hay datos: continuar a fallback (no logar warning spurious)
        except Exception:
            pass

        # 2. Fallback: Usar última ubicación guardada en base de datos
        try:
            db_path = 'local_gastos.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT latitud, longitud, fuente_gps "
                "FROM transacciones "
                "WHERE latitud IS NOT NULL AND longitud IS NOT NULL "
                "ORDER BY fecha_hora_epoch DESC LIMIT 1"
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                lat, lng, fuente = row
                return {
                    'latitud': float(lat),
                    'longitud': float(lng),
                    'fuente_gps': fuente
                }
        except Exception:
            pass

        return None

    def solicitar_motivo_contexto(self, es_gasto: bool, titulo_notificacion: str = "", app_nombre: str = "") -> str:
        """Solicita el motivo al usuario con contexto."""
        tipo_str = "GASTO" if es_gasto else "INGRESO"
        mensaje = f"[{tipo_str}] ¿Cuál fue el motivo de este {['gastado', 'ingresado'][es_gasto]}? (app: {app_nombre})"

        try:
            resultado = self.mostrar_dialogo(
                widget="text",
                titulo=f"[{tipo_str}] Motivo",
                mensaje=mensaje,
            )

            if resultado and "text" in resultado:
                motivo = resultado["text"].strip()
                if motivo:
                    return motivo
                return "Sin motivo especificado"
            return "Sin motivo especificado"
        except Exception:
            return "Sin motivo especificado"

    def solicitar_monto_contexto(self, es_gasto: bool, app_nombre: str = "") -> Optional[Dict]:
        """Solicita el monto al usuario."""
        if es_gasto:
            monto_tipo = "gastado"
        else:
            monto_tipo = "ingresado"

        mensaje = f"[TIPO] ¿Ingrese el monto {monto_tipo}? (app: {app_nombre})"
        mensaje = mensaje.replace("[TIPO]", "GASTO" if es_gasto else "INGRESO")

        try:
            resultado = self.mostrar_dialogo(
                widget="counter",
                titulo=f"[{'GASTO' if es_gasto else 'INGRESO'}] Monto",
                mensaje=mensaje,
                r="1,10000,1",
            )

            if resultado and "r" in resultado:
                try:
                    monto = float(resultado["r"])
                    if monto > 0:
                        return {"monto": monto, "widget": "counter"}
                except ValueError:
                    pass
            if resultado and "text" in resultado:
                try:
                    monto = float(resultado["text"])
                    if monto > 0:
                        return {"monto": monto, "widget": "text"}
                except ValueError:
                    pass
            return None
        except Exception:
            return None

    def solicitar_destinatario_contexto(self, es_gasto: bool, app_nombre: str = "") -> str:
        """Solicita el destinatario."""
        tipo_str = "GASTO" if es_gasto else "INGRESO"
        mensaje = f"[{tipo_str}] ¿Quién es el persona o comercio? (app: {app_nombre})"

        try:
            resultado = self.mostrar_dialogo(
                widget="text",
                titulo=f"[{tipo_str}] Destinatario",
                mensaje=mensaje,
            )

            if resultado and "text" in resultado:
                destinatario = resultado["text"].strip()
                if destinatario:
                    return destinatario
            return "por definir"
        except Exception:
            return "por definir"

    def obtener_gps_directo(self, timeout: int = 10) -> Optional[Dict[str, float]]:
        """Obtiene ubicación GPS usando termux-location con ruta explícita."""
        try:
            cmd_path = self._get_command_path("location")
            if not cmd_path:
                return None

            args = ["-g", str(timeout)]
            output = subprocess.run(
                [cmd_path] + args,
                capture_output=True, text=True, timeout=timeout + 5
            )

            if not output or output.returncode != 0:
                return None

            import json
            ubicacion = json.loads(output.stdout)
            lat = ubicacion.get("lat")
            lng = ubicacion.get("lon")

            if lat is not None and lng is not None:
                return {
                    "latitud": float(lat),
                    "longitud": float(lng),
                    "fuente_gps": "live"
                }
        except (json.JSONDecodeError, FileNotFoundError):
            pass
        except Exception as e:
            logger.debug(f"Error GPS directo: {e}")

        return None

    def remover_notificacion(self, notification_id: int) -> bool:
        """Marca una notificación como procesada."""
        try:
            cmd_path = self._get_command_path("notification_remove")
            if not cmd_path:
                return False

            output = subprocess.run(
                [cmd_path, str(notification_id)],
                capture_output=True, text=True, timeout=5
            )
            return output is not None and output.returncode == 0
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def verificar_salud(self) -> Dict[str, bool]:
        """Retorna el estado de salud de todos los comandos Termux.

        Verifica bajo demanda si los comandos aún no se han verificado.
        """
        if self._available_commands is None:
            self._available_commands = self._check_available_commands()
        return self._available_commands.copy()


# Instancia global - importa desde main.py o usa la definida aquí
# Esta línea permite que otros módulos hagan: from modulios.termux_api import termux_api
termux_api = TermuxAPI()