"""Implementación de InputProvider para Termux usando termux-dialog.

Todas las methods retoran el mismo formato JSON estandarizado:
{"code": 0|-1, "text": "", "raw": "", "valid": true|false, "error": null|str}
"""

import subprocess
import json


class TermuxInputProvider:
    """Implementación para Termux usando termux-dialog"""
    
    def _ejecutar_dialog(self, comando: list, timeout: int = 30) -> dict:
        """Ejecuta termux-dialog y retorna JSON estandarizado"""
        try:
            result = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            texto_salida = result.stdout.strip() if result.stdout else ""
            
            return {
                "code": 0 if result.returncode == 0 else -1,
                "text": texto_salida,
                "raw": texto_salida,
                "valid": result.returncode == 0 and bool(texto_salida.strip()),
                "error": None if result.returncode == 0 else "error_en_dialog"
            }
        except subprocess.TimeoutExpired:
            return {
                "code": -1,
                "text": "",
                "raw": "",
                "valid": False,
                "error": "timeout_expirado"
            }
        except Exception as e:
            return {
                "code": -1,
                "text": "",
                "raw": str(e),
                "valid": False,
                "error": str(e)
            }
    
    def solicitar_texto(self, pregunta: str, timeout: int = 30) -> dict:
        """Solicita texto usando termux-dialog --input"""
        cmd = ["termux-dialog", "--input", pregunta]
        return self._ejecutar_dialog(cmd, timeout)
    
    def solicitar_numero(self, pregunta: str, min_val: float = None, max_val: float = None) -> dict:
        """Solicita número usando termux-dialog --input, luego valida"""
        resultado = self.solicitar_texto(pregunta, timeout)
        
        if resultado["code"] != 0 or not resultado["text"]:
            return resultado
        
        # Validar que sea número
        try:
            valor = float(resultado["text"])
            # Validar rango si se especifica
            if min_val is not None and valor < min_val:
                resultado["code"] = -1
                resultado["text"] = ""
                resultado["valid"] = False
                resultado["error"] = f"numero_debe_se_mayor_igual_a_{min_val}"
                return resultado
            if max_val is not None and valor > max_val:
                resultado["code"] = -1
                resultado["text"] = ""
                resultado["valid"] = False
                resultado["error"] = f"numero_debe_menor_igual_a_{max_val}"
                return resultado
            
            # Actualizar text con el número validado
            resultado["text"] = str(valor)
            resultado["valid"] = True
            resultado["error"] = None
            return resultado
        except ValueError:
            resultado["code"] = -1
            resultado["text"] = ""
            resultado["valid"] = False
            resultado["error"] = "no_es_un_numero_valido"
            return resultado
    
    def solicitar_confirmacion(self, pregunta: str) -> dict:
        """Solicita confirmación S/N usando termux-dialog"""
        cmd = ["termux-dialog", "--yesno", f"{pregunta}\n(Responda: s/n)", 8, 40]
        resultado = self._ejecutar_dialog(cmd, 30)
        
        if resultado["code"] == 0 and resultado["text"].lower() in ("s", "yes", "y"):
            resultado["text"] = "true"
            resultado["valid"] = True
            resultado["error"] = None
        else:
            resultado["text"] = "false"
            resultado["valid"] = False
            resultado["error"] = "usuario_no_confirmo" if resultado["code"] == 0 else "error_en_dialog"
        
        return resultado