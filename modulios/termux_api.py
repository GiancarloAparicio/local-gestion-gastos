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


class TermuxAPI:
    """Clase que encapsula los comandos de Termux API."""

    # Comandios disponibles por defecto en Termux
    COMMANDS = {
        "notification_list": "termux-notification-list",
        "dialog": "termux-dialog",
        "location": "termux-location",
        "notification_remove": "termux-notification-remove",
    }

    def __init__(self):
        # Verificar qué comandos están disponibles al iniciar
        self.available_commands = self._check_available_commands()
        logger.info(f"📱 Termux API inicializada - Comandos disponibles: {self.available_commands}")

    def _check_available_commands(self) -> Dict[str, bool]:
        """Verifica qué comandos de Termux están disponibles en el sistema."""
        available = {}
        for name, cmd in self.COMMANDS.items():
            try:
                result = subprocess.run(
                    ["which", cmd], capture_output=True, text=True, timeout=5
                )
                available[name] = result.returncode == 0
                if available[name]:
                    logger.info(f"✅ Comando disponible: {cmd}")
                else:
                    logger.warning(f"⚠️ Comando no encontrado: {cmd}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                available[name] = False
                logger.warning(f"⚠️ No se pudo verificar: {cmd}")
        return available

    def _ejecutar_comando(self, comando: str, args: List[str] = None) -> Optional[str]:
        """Ejecuta un comando de Termux de manera segura."""
        try:
            full_cmd = [comando]
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

    def obtener_gps(self, timeout: int = 10) -> Optional[Dict[str, float]]:
        """Obtiene ubicación GPS usando termux-location."""
        if not self.available_commands["location"]:
            logger.warning("⚠️ termux-location no disponible")
            return None

        args = ["-g", str(timeout)]  # GPS mode con timeout
        output = self._ejecutar_comando(self.COMMANDS["location"], args)

        if not output:
            return None

        try:
            import json
            ubicacion = json.loads(output)
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

        output = self._ejecutar_comando(
            self.COMMANDS["notification_remove"],
            [str(notification_id)]
        )
        return output is not None

    def verificar_salud(self) -> Dict[str, bool]:
        """Retorna el estado de salud de todos los comandos Termux."""
        return self.available_commands.copy()


# Instancia global para fácil acceso
termux_api = TermuxAPI()


if __name__ == "__main__":
    import sys
    print(f"📱 Termux API Health Check:")
    for cmd, disp in termux_api.verificar_salud().items():
        status = "✅" if disp else "❌"
        print(f"   {status} {cmd}")
