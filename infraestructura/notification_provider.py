"""Módulo de proveedor de notificaciones bancarias.
Captura notificaciones en Termux y Linux, siempre retornando el mismo formato JSON estandarizado:
{"code": 0|-1, "data": {"paquete": "", "app": "", "titulo": "", "mensaje": "", "monto": float|None, 
 "tipo": "ingreso"|"gasto"|"indeterminado", "destinatario": "", "event_id": "", "timestamp": float,
 "canal": "yape"|"interbank"|"bbva"|..., "motivo": None, "mensaje_raw": ""}, 
 "raw": "", "valid": true|false, "error": null|str}
"""

from abc import ABC, abstractmethod
import json
import re
import time


class NotificationProvider(ABC):
    """Provedor abstracto de notificaciones bancarias."""
    
    @abstractmethod
    def capturar_notificacion(self) -> dict:
        """Capturar una notificación. Retorna JSON estandarizado normalizado."""
        pass
    
    @abstractmethod
    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Verificar si los datos crudos corresponden a un banco conocido."""
        pass
    
    @abstractmethod
    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convertir datos crudos a diccionario normalizado estandarizado."""
        pass


class TermuxNotificationProvider(NotificationProvider):
    """Implementación para Termux - captura vía API nativa/termux-API"""
    
    def _extraer_monto(self, mensaje: str) -> float | None:
        """Extraer monto del mensaje de notificación"""
        patrones = [
            r"S/\s*[\d,]+\.?\d*",  # S/ 50.00 o S/ 10
            r"[\d,]+\.?\d*\s*soles",
            r"[\d,]+\.?\d*\s*pen"
        ]
        
        for patron in patrones:
            match = re.search(patron, mensaje)
            if match:
                numero_str = match.group(0)
                numero_limpio = re.sub(r"[S/s/\s]", "", numero_str)
                try:
                    return float(numero_limpio.replace(",", "."))
                except ValueError:
                    continue
        
        return None
    
    def _determinar_tipo(self, mensaje: str) -> str:
        """Determinar si es ingreso o gasto"""
        mensaje_lower = mensaje.lower()
        
        patrones_ingreso = ["te envió un pago", "te transferenció", "te abonó"]
        patrones_gasto = ["Plineaste", "gastaste", "debité", "cargo por"]
        
        for p in patrones_ingreso:
            if p in mensaje_lower:
                return "ingreso"
        
        for p in patrones_gasto:
            if p in mensaje_lower:
                return "gasto"
        
        return "indeterminado"
    
    def _extraer_destinatario(self, mensaje: str) -> str:
        """Extraer nombre de destinatario después de 'a '"""
        match = re.search(r"a\s+([A-Za-zÁÉÍÓÚñÑ\s]+?)(?:\s+$|\,|\.)", mensaje)
        if match:
            return match.group(1).strip()
        return "desconocido"
    
    def _determinar_canal(self, paquete: str) -> str:
        """Determinar canal basado en paquete"""
        mapeo = {
            "com.bcp.innovacxion.yapeapp": "yape",
            "pe.com.interbank.mobilebanking": "interbank",
            "com.bbva.bancomovil": "bbva",
            "manual": "manual"
        }
        return mapeo.get(paquete, "desconocido")
    
    def capturar_notificacion(self) -> dict:
        """Capturar notificación actual en Termux"""
        # En Termux intentar obtener via termux-API o polling
        # Por ahora simulamos obteniendo la última notificación disponible
        
        # Intentar parsear output de termux-notifications si está disponible
        try:
            result = subprocess.run(
                ["termux-notifications"],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout
            
            # Parsear notificaciones del output
            # Formato típico de termux-notifications:
            # ID | TAG | KEY | GROUP | PACKAGENAME | TITLE | CONTENT | WHEN
            # Dividir por líneas y tomar la última
            lineas = [l for l in output.split("\n") if l.strip()]
            
            if not lineas:
                return {
                    "code": -1,
                    "data": {},
                    "raw": "no_hay_notificaciones_actualmente",
                    "valid": False,
                    "error": "no_hay_notificaciones"
                }
            
            # Tomar la última línea (más reciente)
            ultima_notif = lineas[-1]
            partes = [p.strip() for p in ultima_notif.split("|")]
            
            if len(partes) >= 7:
                paquete = partes[4] if len(partes) > 4 else ""
                titulo = partes[5] if len(partes) > 5 else ""
                mensaje = partes[6] if len(partes) > 6 else ""
                when_str = partes[7] if len(partes) > 7 else str(time.time())
                
                # Parsear cuando
                try:
                    if "/" in when_str:
                        # Formato "YYYY-MM-DD HH:MM:SS"
                        from datetime import datetime
                        dt = datetime.strptime(when_str, "%Y-%m-%d %H:%M:%S")
                        timestamp = dt.timestamp()
                    else:
                        timestamp = float(when_str)
                except:
                    timestamp = time.time()
                
                # Normalizar a nuestro formato estandarizado
                normalizado = {
                    "paquete": paquete,
                    "app": titulo,
                    "titulo": titulo,
                    "mensaje": mensaje,
                    "monto": self._extraer_monto(mensaje),
                    "tipo": self._determinar_tipo(mensaje),
                    "destinatario": self._extraer_destinatario(mensaje),
                    "event_id": partes[1] if len(partes) > 1 else "",  # KEY field
                    "timestamp": timestamp,
                    "canal": self._determinar_canal(paquete),
                    "motivo": None,  # Siempre None inicialmente - se solicita después
                    "mensaje_raw": mensaje
                }
                
                return {
                    "code": 0,
                    "data": normalizado,
                    "raw": output,
                    "valid": normalizado["monto"] is not None or normalizado["tipo"] is not None,
                    "error": None
                }
            
        except FileNotFoundError:
            pass
        except Exception as e:
            pass
        
        # Fallback: si no hay termux-notifications disponible, retornar estructura vacía
        return {
            "code": -1,
            "data": {},
            "raw": "error_captiendo_notificaciones_termux",
            "valid": False,
            "error": str(e) if e else "metodo_no_disponible"
        }
    
    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Verificar si los datos crudos son de un banco conocido"""
        paquete = datos_crudos.get("packageName", datos_crudos.get("package", ""))
        
        paquetes_conocidos = [
            "com.bcp.innovacxion.yapeapp",
            "pe.com.interbank.mobilebanking",
            "com.bbva.bancomovil",
            "manual"
        ]
        
        return paquete in paquetes_conocidos
    
    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convertir datos crudos a formato normalizado estandarizado"""
        mensaje = datos_crudos.get("content", datos_crudos.get("message", ""))
        
        return {
            "paquete": datos_crudos.get("packageName", datos_crudos.get("package", "")),
            "app": datos_crudos.get("title", ""),
            "titulo": datos_crudos.get("title", ""),
            "mensaje": mensaje,
            "monto": self._extraer_monto(mensaje),
            "tipo": self._determinar_tipo(mensaje),
            "destinatario": self._extraer_destinatario(mensaje),
            "event_id": datos_crudos.get("key", datos_crudos.get("notification_id", ""))[:50],
            "timestamp": float(datos_crudos.get("when", datos_crudos.get("timestamp", time.time()))),
            "canal": self._determinar_canal(datos_crudos.get("packageName", datos_crudos.get("package", ""))),
            "motivo": None,
            "mensaje_raw": mensaje
        }


class LinuxNotificationProvider(NotificationProvider):
    """Implementación para Linux - captura mediante monitoring o input manual"""
    
    def capturar_notificacion(self) -> dict:
        """En Linux, las notificaciones pueden venir de distintas fuentes.
        Por ahora, indicamos al usuario que puede ingresar datos manualmente
        o estamos monitoring un directorio de archivos JSON de Automate."""
        
        # En un sistema completo, aquí monitoring de directorios,
        # DBus notifications, o input manual por CLI
        return {
            "code": -1,
            "data": {},
            "raw": "en_linux_monitoring_o_input_manual",
            "valid": False,
            "error": "notificaciones_sistema_distintas_requiere_monitoring"
        }
    
    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Verificar en Linux si es notificación de banco conocido"""
        # En Linux, los datos crudos tendrían estructura distinta
        paquete = datos_crudos.get("paquete", "")
        conocido = paquete in ["yape", "interbank", "bbva", "manual"]
        return conocido
    
    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Normalizar notificación en Linux - estructura adaptada"""
        return {
            "paquete": datos_crudos.get("paquete", ""),
            "app": datos_crudos.get("app", ""),
            "titulo": datos_crudos.get("titulo", ""),
            "mensaje": datos_crudos.get("mensaje", ""),
            "monto": datos_crudos.get("monto"),
            "tipo": datos_crudos.get("tipo", "indeterminado"),
            "destinatario": datos_crudos.get("destinatario", ""),
            "event_id": datos_crudos.get("event_id", ""),
            "timestamp": datos_crudos.get("timestamp", time.time()),
            "canal": datos_crudos.get("canal", "desconocido"),
            "motivo": None,
            "mensaje_raw": datos_crudos.get("mensaje_raw", "")
        }


class NotificationFactory:
    """Factoría para crear el proveedor de notificaciones según el entorno"""
    
    @staticmethod
    def detectar_entorno() -> str:
        """Detecta si estamos en Termux o Linux"""
        import os
        import sys
        
        termux_signs = ["ANDROID_DATA", "EXTERNAL_STORAGE", "com.termux", "TERMUX_VERSION"]
        for sign in termux_signs:
            if sign in os.environ:
                return "termux"
        
        if sys.platform.startswith("linux") and not any(sign in os.environ for sign in termux_signs):
            return "linux"
        
        return "linux"
    
    @staticmethod
    def crear_proveedor() -> NotificationProvider:
        """Crea el proveedor de notificaciones apropiado"""
        entorno = NotificationFactory.detectar_entorno()
        
        if entorno == "termux":
            return TermuxNotificationProvider()
        else:
            return LinuxNotificationProvider()