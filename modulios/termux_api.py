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

# Ruta por defecto de Termux (se sobreescribe desde main.py usando config.yaml)
TERMUX_PATH = "/data/data/com.termux/files/usr/bin"

COMMANDS = {
    "notification_list": "termux-notification-list",
    "dialog": "termux-dialog",
    "location": "termux-location",
    "notification_remove": "termux-notification-remove",
}


class TermuxAPI:
    """Clase que encapsula los comandos de Termux API."""

    # COMMANDS como atributo de clase (fijo error AttributeError original)
    COMMANDS = {
        "notification_list": "termux-notification-list",
        "dialog": "termux-dialog",
        "location": "termux-location",
        "notification_remove": "termux-notification-remove",
    }
    # Control para logging una sola vez al crear la instancia global
    _logging_done = False

    def __init__(self, termux_path=None):
        # Usar ruta proporcionada o la por defecto
        self.termux_path = termux_path or TERMUX_PATH
        # Validar comandos al iniciar - recolecta datos sin logs internos
        self.available_commands = self._check_available_commands()
        # Logueo basado en resultados: informar al usuario qué comandos hay
        # Solo loguear en la primera instancia para evitar duplicados (control de clase)
        if not TermuxAPI._logging_done:
            TermuxAPI._logging_done = True
            cmd_names = list(self.available_commands.keys())
            all_found = all(self.available_commands.values())
            if all_found:
                logger.info(f"📱 Termux API inicializada - ✅ Todos los comandos disponibles: {cmd_names}")
            elif any(self.available_commands.values()):
                # Algunos comandos encontrados, algunos no
                found = [k for k, v in self.available_commands.items() if v]
                not_found = [k for k, v in self.available_commands.items() if not v]
                logger.warning(f"⚠️ Termux API inicializada - Mezcla: {found} disponibles, {not_found} no")
            else:
                # Ningún comando encontrado
                logger.warning(f"⚠️ Termux API inicializada - ❌ Ningún comando disponible: {cmd_names}")

    def _get_command_path(self, cmd_name):
        """Obtiene la ruta completa de un comando de Termux usando self.termux_path."""
        cmd_name = self.COMMANDS.get(cmd_name)
        if not cmd_name:
            return None
        return os.path.join(self.termux_path, cmd_name)

    def _check_available_commands(self) -> Dict[str, bool]:
        """Verifica qué comandos de Termux están disponibles en el sistema.
        
        Intenta ejecutar cada comando con --version. Si falla por FileNotFoundError,
        es porque el binario no está en la ruta configurada - informativo para el usuario.
        Si el comando se ejecuta (retorno 0), está disponible.
        """
        available = {}
        for name, cmd in self.COMMANDS.items():
            try:
                cmd_path = self._get_command_path(name)
                if cmd_path:
                    # Intentamos verificar el comando
                    result = subprocess.run(
                        [cmd_path, "--version"], capture_output=True, text=True, timeout=5
                    )
                    available[name] = result.returncode == 0
                else:
                    available[name] = False
            except FileNotFoundError:
                # El directorio o binario no existe en la ruta configurada
                # Esto es informativo: el usuario sabe que Termux no está configurado bien
                available[name] = False
                logger.debug(f"⚠️ Comando no verificado: {name} (binario no en {self.termux_path})")
            except (subprocess.TimeoutExpired, OSError):
                # Timeout u otros errores de sistema
                available[name] = False
            except Exception as e:
                # Cualquier otro error inesperado
                available[name] = False
        
        # Este método solo recolecta datos, no emite logs:
        # El caller (__init__) decidirá qué logar
        return available

    def _ejecutar_comando(self, comando_nombre: str, args: List[str] = None) -> Optional[str]:
        """Ejecuta un comando de Termux de manera segura.
        
        Returns None si el comando no existe o falla - el sistema se degrada gracefully.
        """
        try:
            cmd_path = self._get_command_path(comando_nombre)
            if not cmd_path:
                logger.error(f"Comando no encontrado en la ruta configurada: {comando_nombre}")
                return None

            full_cmd = [cmd_path]
            if args:
                full_cmd.extend(args)

            logger.debug(f"Ejecutando comando Termux: {' '.join(full_cmd)}")
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                return result.stdout.strip() if result.stdout else None
            else:
                # Comando existe pero falló - logueamos error pero no levantamos excepción
                logger.error(f"Error en comando Termux ({comando_nombre}): {result.stderr[:100]}")
                return None
        except FileNotFoundError:
            # Binario no existe en esta ruta - esperado fuera de Termux
            logger.debug(f"⚠️ Binario no encontrado en {cmd_path} (no estás en Termux?)")
            return None
        except Exception as e:
            logger.error(f"❌ Error ejecutando comando Termux: {e}")
            return None

    def mostrar_dialogo(self, widget: str = "text", titulo: str = None,
                        mensaje: str = "", **kwargs) -> Optional[Dict]:
        """Muestra un diálogo usando termux-dialog.
        
        Si termux-dialog no está disponible, retorna None y el llamador decidirá qué hacer.
        """
        if not self.available_commands["dialog"]:
            logger.debug("⚠️ termux-dialog no disponible - modo diálogo desactivado")
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
            logger.info(f"💬 Diálogo termux finalizado: {resultado}")
            return resultado
        except json.JSONDecodeError:
            logger.warning(f"⚠️ Salida no JSON del diálogo: {output}")
            return {"raw": output}

    def obtener_gps(self, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """Obtiene ubicación GPS con fallback a base de datos.
        
        PRIMERO intenta GPS en tiempo real con termux-location.
        Si falla (no hay Termux o binario no disponible), usa fallback a BD.
        """
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
                # Si returncode != 0 o sin stdout: GPS no disponible, continuar a fallback
                logger.debug(f"⚠️ GPS tiempo real no disponible (returncode={result.returncode})")
            else:
                logger.debug("⚠️ No se pudo construir path para GPS")
        except Exception as e:
            logger.warning(f"⚠️ GPS tiempo real falló: {e}")

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
                logger.info("📡 Usando ubicación última conocida de la base de datos")
                return {
                    'latitud': float(lat),
                    'longitud': float(lng),
                    'fuente_gps': fuente
                }
            # Sin datos en BD tampoco: retornar None (el llamador decidirá)
            logger.debug("⚠️ No hay ubicación GPS disponible (ni en vivo ni en BD)")
        except Exception as e:
            logger.error(f"❌ Error en fallback GPS BD: {e}")

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
                logger.debug("⚠️ No se pudo obtener path para GPS directo")
                return None

            args = ["-g", str(timeout)]
            output = subprocess.run(
                [cmd_path] + args,
                capture_output=True, text=True, timeout=timeout + 5
            )

            if not output or output.returncode != 0:
                # Comando existió pero no retornó datos - GPS no disponible ahora
                logger.debug(f"⚠️ GPS directo no retornó datos (returncode={output.returncode if output else 'N/A'})")
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
            else:
                logger.debug("⚠️ GPS directo sin lat/lng en salida")
                return None
        except (json.JSONDecodeError, FileNotFoundError):
            # Archivo no encontrado o JSON inválido - fuera de Termux
            logger.debug("⚠️ GPS directo: error de JSON o binario no encontrado")
            return None
        except Exception as e:
            logger.error(f"❌ Error GPS directo: {e}")
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
            # Return True solo si returncode es 0 (éxito real)
            # Si es None o distinto de 0, retorno False (no pudimos remover)
            return output is not None and output.returncode == 0
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def verificar_salud(self) -> Dict[str, bool]:
        """Retorna el estado de salud de todos los comandos Termux."""
        return self.available_commands.copy()


# Instancia global - importa desde main.py o usa la definida aquí
# Esta línea permite que otros módulos hagan: from modulios.termux_api import termux_api
termux_api = TermuxAPI()