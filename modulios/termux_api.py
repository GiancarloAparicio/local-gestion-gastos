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

# Ruta por defecto de Termux (se sobreescribirá desde main.py si es necesario)
TERMUX_PATH = "/data/data/com.termux/files/usr/bin"

COMMANDS = {
    "notification_list": "termux-notification-list",
    "dialog": "termux-dialog",
    "location": "termux-location",
    "notification_remove": "termux-notification-remove",
}


class TermuxAPI:
    """Clase que encapsula los comandos de Termux API."""

    # COMMANDS es un atributo de clase compartido por todas las instancias
    COMMANDS = {
        "notification_list": "termux-notification-list",
        "dialog": "termux-dialog",
        "location": "termux-location",
        "notification_remove": "termux-notification-remove",
    }

    def __init__(self, termux_path=None):
        # Usar la ruta proporcionada o la por defecto
        self.termux_path = termux_path or TERMUX_PATH
        # Verificar qué comandos están disponibles al iniciar
        self.available_commands = self._check_available_commands()
        logger.info(f"📱 Termux API inicializada - Comandos disponibles: {self.available_commands}")

    def _get_command_path(self, cmd_name):
        """Obtiene la ruta completa de un comando de Termux."""
        cmd_name = self.COMMANDS.get(cmd_name)
        if not cmd_name:
            return None
        return os.path.join(self.termux_path, cmd_name)

    def _check_available_commands(self) -> Dict[str, bool]:
        """Verifica qué comandos de Termux están disponibles en el sistema."""
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
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                available[name] = False
            if available[name]:
                logger.info(f"✅ Comando disponible: {name}")
            else:
                logger.warning(f"⚠️ Comando no encontrado: {name}")
        return available

    def _ejecutar_comando(self, comando_nombre: str, args: List[str] = None) -> Optional[str]:
        """Ejecuta un comando de Termux de manera segura."""
        try:
            cmd_path = self._get_command_path(comando_nombre)
            if not cmd_path:
                logger.error(f"Comando no encontrado en la ruta configurada: {comando_nombre}")
                return None
            
            full_cmd = [cmd_path]
            if args:
                full_cmd.extend(args)

            logger.debug(f"Ejecutando: {' '.join(full_cmd)}")
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                return result.stdout.strip() if result.stdout else None
            else:
                logger.error(f"Error en comando Termux: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("❌ Tiempo de espera agotado al ejecutar comando Termux")
            return None
        except Exception as e:
            logger.error(f"❌ Error ejecutando comando Termux: {e}")
            return None

    def mostrar_dialogo(self, widget: str = "text", titulo: str = None,
                        mensaje: str = "", **kwargs) -> Optional[Dict]:
        """Muestra un diálogo usando termux-dialog.

        Soporta varios widgets:
        - text: Input de texto (default)
        - radio: Botones de radio
        - checkbox: Checkboxes múltiples
        - spinner: Dropdown
        - counter: Contador de número
        - date: Selector de fecha
        - time: Selector de hora
        - sheet: Hoja deslizable
        - confirm: Cuadro de confirmación

        Ejemplo:
        termux_api.mostrar_dialogo(
            widget="text",
            titulo="Monto",
            mensaje="¿Cuánto fue el gasto?",
            n  # modo números
        )

        Returns:
            Diccionario con los resultados del diálogo o None si falla
        """
        if not self.available_commands["dialog"]:
            logger.warning("⚠️ termux-dialog no disponible")
            return {"text": mensaje, "widget": widget} if mensaje else None

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

        Primero intenta obtener GPS en tiempo real con termux-location.
        Si falla o se demora mucho, usa la última ubicación guardada en la base de datos.

        Args:
            timeout: Segundos máxima espera para termux-location (default 15s)

        Returns:
            Diccionario con lat, lng y fuente_gps, o None si no hay datos
        """
        import json
        import subprocess
        import sqlite3

        # 1. Intentar GPS en tiempo real
        try:
            result = subprocess.run(
                [self._get_command_path("location"), "-g", str(timeout)],
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
                return {
                    'latitud': float(lat),
                    'longitud': float(lng),
                    'fuente_gps': fuente
                }
        except Exception as e:
            logger.error(f"❌ Error en fallback GPS BD: {e}")

        return None


    def solicitar_motivo_contexto(self, es_gasto: bool, titulo_notificacion: str = "", app_nombre: str = "") -> str:
        """Solicita el motivo al usuario con contexto sobre el tipo de movimiento y la aplicación.
        
        Formato del mensaje: [TIPO] ¿Cuál fue el motivo de este [tipo]? (app: APP_NOMBRE)
        
        Args:
            es_gasto: True si es un gasto, False si es un ingreso
            titulo_notificacion: Título de la notificación original (ej. "Interbank", "Yape")
            app_nombre: Nombre de la aplicación (ej. "BBVA", "Yape", "Plin", "NFC")
            
        Returns:
            El motivo ingresado por el usuario o "Sin motivo especificado" si cancela
        """
        # Construir el mensaje con el tipo PRIMERO
        tipo_str = "GASTO" if es_gasto else "INGRESO"
        
        # Determinar si es gasto o ingreso para el mensaje de monto
        if es_gasto:
            monto_tipo = "gastado"
        else:
            monto_tipo = "ingresado"
            
        # Construir el mensaje con el tipo PRIMERO, según la solicitud del usuario
        # Formato: [TIPO] ¿Cuál fue el motivo de este [tipo]? (app: APP_NOMBRE)
        mensaje = f"[{tipo_str}] ¿Cuál fue el motivo de este {monto_tipo}? (app: {app_nombre})"
        
        # Mostrar el diálogo de texto
        try:
            resultado = self.mostrar_dialogo(
                widget="text",
                titulo=f"[{tipo_str}] Motivo",  # Título muestra el tipo
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
        """Solicita el monto al usuario con contexto sobre si es gasto o ingreso.
        
        Formato del mensaje: [TIPO] ¿Ingrese el monto [gastado/ingresado]? (app: APP_NOMBRE)
        
        Args:
            es_gasto: True si es un gasto, False si es un ingreso
            app_nombre: Nombre de la aplicación
            
        Returns:
            Diccionario con el resultado del diálogo o None
        """
        # Determinar el texto dependiendo si es gasto o ingreso
        if es_gasto:
            monto_tipo = "gastado"
        else:
            monto_tipo = "ingresado"
            
        # Construir el mensaje con el tipo PRIMERO
        mensaje = f"[TIPO] ¿Ingrese el monto {monto_tipo}? (app: {app_nombre})"
        # Reemplazar TIPO por el tipo real
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
        """Solicita el destinatario con contexto del tipo de movimiento.
        
        Formato: [TIPO] ¿Quién es el persona o comercio? (app: APP_NOMBRE)
        
        Args:
            es_gasto: True si es un gasto, False si es un ingreso
            app_nombre: Nombre de la aplicación
            
        Returns:
            El destinatario ingresado por el usuario
        """
        # Construir el mensaje
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
        if not self.available_commands["location"]:
            logger.warning("⚠️ termux-location no disponible")
            return None

        cmd_path = self._get_command_path("location")
        if not cmd_path:
            return None

        args = ["-g", str(timeout)]  # GPS mode con timeout
        output = subprocess.run(
            [cmd_path] + args,
            capture_output=True, text=True, timeout=timeout + 5
        )

        if not output or output.returncode != 0:
            return None

        try:
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
                return self._obtener_ultima_gps()
        except json.JSONDecodeError:
            logger.error("❌ No se pudo parsear la salida GPS")
            return None

    def _obtener_ultima_gps(self) -> Optional[Dict[str, float]]:
        """Obtiene la última ubicación conocida."""
        logger.info("📡 Obteniendo última ubicación conocida...")
        return {
            "latitud": None,
            "longitud": None,
            "fuente_gps": "last_known"
        }

    def remover_notificacion(self, notification_id: int) -> bool:
        """Marca una notificación como procesada."""
        if not self.available_commands["notification_remove"]:
            logger.warning("⚠️ termux-notification-remove no disponible")
            return False

        cmd_path = self._get_command_path("notification_remove")
        if not cmd_path:
            return False

        output = subprocess.run(
            [cmd_path, str(notification_id)],
            capture_output=True, text=True, timeout=5
        )
        return output is not None and output.returncode == 0

    def verificar_salud(self) -> Dict[str, bool]:
        """Retorna el estado de salud de todos los comandos Termux."""
        return self.available_commands.copy()


# Instancia global para fácil acceso
termux_api = TermuxAPI()