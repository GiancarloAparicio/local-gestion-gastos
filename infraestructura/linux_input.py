"""Implementación de InputProvider para Linux standard usando input() de Python.

Todas las methods retoran el mismo formato JSON estandarizado que Termux:
{"code": 0|-1, "text": "", "raw": "", "valid": true|false, "error": null|str}
"""

import sys


class LinuxInputProvider:
    """Implementación para Linux standard usando input() de Python"""
    
    def _validar_texto(self, texto: str) -> bool:
        """Validación básica de texto no vacío"""
        return texto and texto.strip()
    
    def _validar_numero(self, texto: str, min_val: float = None, max_val: float = None) -> tuple:
        """Valida si es número y retorna (es_valido, valor_o_None)"""
        try:
            valor = float(texto)
            if min_val is not None and valor < min_val:
                return False, None
            if max_val is not None and valor > max_val:
                return False, None
            return True, valor
        except (ValueError, TypeError):
            return False, None
    
    def solicitar_texto(self, pregunta: str, timeout: int = 30) -> dict:
        """Solicita texto usando input() de Python"""
        try:
            print(f"\n{pregunta}", flush=True)
            texto = input().strip()
            
            return {
                "code": 0 if self._validar_texto(texto) else -1,
                "text": texto if self._validar_texto(texto) else "",
                "raw": texto,
                "valid": self._validar_texto(texto),
                "error": None if self._validar_texto(texto) else "entrada_vacia"
            }
        except (KeyboardInterrupt, EOFError):
            return {
                "code": -1,
                "text": "",
                "raw": "",
                "valid": False,
                "error": "cancelado_por_usuario"
            }
    
    def solicitar_numero(self, pregunta: str, min_val: float = None, max_val: float = None) -> dict:
        """Solicita número usando input(), valida y retorna JSON estandarizado"""
        resultado = self.solicitar_texto(pregunta, timeout=30)
        
        if resultado["code"] != 0 or not resultado["text"]:
            return resultado
        
        # Validar y convertir a número
        es_valido, valor = self._validar_numero(resultado["text"], min_val, max_val)
        
        if es_valido:
            resultado["text"] = str(valor)
            resultado["valid"] = True
            resultado["error"] = None
            resultado["code"] = 0
        else:
            resultado["text"] = ""
            resultado["valid"] = False
            if min_val is not None and max_val is not None:
                resultado["error"] = f"numero_debe_estar_between_{min_val}_and_{max_val}"
            elif min_val is not None:
                resultado["error"] = f"numero_debe_se_mayor_igual_a_{min_val}"
            else:
                resultado["error"] = "no_es_un_numero_valido"
        
        return resultado
    
    def solicitar_confirmacion(self, pregunta: str) -> dict:
        """Solicita confirmación S/N"""
        print(f"\n{pregunta} (s/n): ", flush=True)
        try:
            resp = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            return {
                "code": -1,
                "text": "",
                "raw": "",
                "valid": False,
                "error": "cancelado_por_usuario"
            }
        
        if resp in ("s", "yes", "y", "si"):
            return {
                "code": 0,
                "text": "true",
                "raw": resp,
                "valid": True,
                "error": None
            }
        elif resp in ("n", "no"):
            return {
                "code": 0,
                "text": "false",
                "raw": resp,
                "valid": True,
                "error": None
            }
        else:
            return {
                "code": -1,
                "text": resp,
                "raw": resp,
                "valid": False,
                "error": "respuesta_no_valida_s_o_n"
            }