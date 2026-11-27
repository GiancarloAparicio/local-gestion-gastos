"""Proveedor de entrada de datos para Termux usando ``termux-dialog``.

``termux-dialog`` retorna JSON con la forma ``{"code": 0, "text": "..."}``
(o ``code: -1`` al cancelar). Este proveedor ejecuta el binario desde
``config.termux.path`` y normaliza esa salida al sobre estándar del sistema:

    {"code": 0|-1, "text": "", "raw": "", "valid": bool, "error": str|None}
"""

import json
import os
import subprocess

from infraestructura import config


def _sobre(code, text="", raw="", error=None):
    return {
        "code": code,
        "text": text,
        "raw": raw,
        "valid": code == 0,
        "error": error,
    }


class TermuxInputProvider:
    """Entrada de usuario mediante diálogos nativos de Termux."""

    def _bin(self, nombre: str) -> str:
        return os.path.join(config.termux_bin(), nombre)

    def _ejecutar(self, args: list, timeout: int = None) -> dict:
        """Ejecuta ``termux-dialog`` con los argumentos dados y parsea su JSON."""
        timeout = timeout or config.timeout_dialogo()
        comando = [self._bin("termux-dialog"), *args]
        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return _sobre(-1, error="termux-dialog_no_disponible")
        except subprocess.TimeoutExpired:
            return _sobre(-1, error="timeout_expirado")
        except Exception as e:  # pragma: no cover - defensivo
            return _sobre(-1, error=str(e))

        salida = (resultado.stdout or "").strip()
        if not salida:
            return _sobre(-1, error="sin_respuesta")

        try:
            datos = json.loads(salida)
        except json.JSONDecodeError:
            # Algunas versiones devuelven texto plano
            return _sobre(0, text=salida, raw=salida)

        code = datos.get("code", 0)
        texto = datos.get("text", "")
        if isinstance(texto, bool):
            texto = "yes" if texto else "no"
        texto = str(texto) if texto is not None else ""
        return _sobre(0 if code in (0, None) else -1, text=texto, raw=salida)

    def solicitar_texto(self, pregunta: str, timeout: int = None) -> dict:
        """Solicita texto libre al usuario."""
        return self._ejecutar(["text", "-t", "Gastos", "-i", pregunta], timeout)

    def solicitar_numero(
        self, pregunta: str, min_val: float = None, max_val: float = None
    ) -> dict:
        """Solicita un número y valida el rango."""
        resultado = self.solicitar_texto(pregunta)
        if resultado["code"] != 0:
            return resultado
        texto = resultado.get("text", "").replace(",", ".").strip()
        # Permitir "S/ 20.50"
        for prefijo in ("S/", "s/", "S/."):
            texto = texto.replace(prefijo, "")
        texto = texto.strip()
        try:
            valor = float(texto)
        except (TypeError, ValueError):
            return _sobre(-1, text="", raw=resultado.get("raw", ""), error="no_es_numero")
        if min_val is not None and valor < min_val:
            return _sobre(-1, text="", raw=texto, error=f"menor_que_{min_val}")
        if max_val is not None and valor > max_val:
            return _sobre(-1, text="", raw=texto, error=f"mayor_que_{max_val}")
        return _sobre(0, text=str(valor), raw=texto)

    def solicitar_confirmacion(self, pregunta: str) -> dict:
        """Solicita confirmación (sí/no)."""
        resultado = self._ejecutar(["confirm", "-t", "Confirmar", "-i", pregunta])
        if resultado["code"] != 0:
            return resultado
        respuesta = resultado.get("text", "").strip().lower()
        afirmativo = respuesta in ("yes", "y", "s", "si", "sí", "true", "1")
        return _sobre(0, text="true" if afirmativo else "false", raw=resultado.get("raw", ""))
