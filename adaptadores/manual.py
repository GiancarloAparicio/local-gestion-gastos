"""ManualAdapter - Adaptador para registros manuales en Termux.

Soporte para registros manuales vía línea de comandos o interacción interactiva
con termux-dialog. Este adaptador se activa cuando el usuario quiere registrar
un gasto o ingreso manualmente (efectivo, transferencias no detectadas, etc.).

Puede operar en dos modos:
1. Modo CLI: Recibe parámetros directamente (--tipo, --monto, etc.)
2. Modo interactivo: Solicita todos los campos vía termux-dialog
"""

import uuid
import sys
import os
import time
from datetime import datetime


class ManualAdapter:
    """Adaptador para registros manuales en Termux."""

    def __init__(self):
        pass

    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """Determina si la notificación es manual.

        En modo CLI, reconoce paquete "manual.entry".
        En modo interactivo, siempre retorna True cuando se solicita un registro manual.
        """
        paquete = (
            datos_crudos.get("paquete")
            or datos_crudos.get("package")
            or datos_crudos.get("packageName", "")
        )
        # Paquete de entrada manual
        return paquete == "manual.entry"

    def normalizar_notificacion(self, datos_crudos: dict = None) -> dict:
        """Solicita al usuario todos los campos necesarios y retorna los datos normalizados.

        En modo interactivo (termux-dialog), pregunta por:
        - Tipo (ingreso/gasto)
        - Monto
        - Destinatario
        - Motivo

        En modo CLI, usa los parámetros proporcionados.

        Returns:
            Diccionario con todos los campos normalizados listos para insertar en SQLite.
        """
        # Modo interactivo: solicitar mediante termux-dialog
        if datos_crudos is None:
            # No hay datos crudos, modo interactivo completo
            return self._solicitar_interactivo()

        # Modo: datos crudos vienen con algunos campos parciales
        # Completar los que falten mediante input/consola
        return self._completar_datos_parciales(datos_crudos)

    def _solicitar_interactivo(self) -> dict:
        """Solicita todos los campos al usuario vía termux-dialog o consola.

        En un dispositivo Android con Termux, esto invocaría:
        termux-dialog text -t "Tipo" -i "¿Es ingreso o gasto?"
        termux-dialog text -t "Monto" -i "¿Cuál es el monto?" -n
        termux-dialog text -t "Destinatario" -i "¿Quién es el destinatario?"
        termux-dialog text -t "Motivo" -i "¿Cuál fue el motivo?"

        Por ahora, simulamos la entrada por consola para desarrollo.
        """
        print("\n" + "=" * 50)
        print("📝 Registro Manual - Ingresar datos")
        print("=" * 50 + "\n")

        # Solicitar tipo
        while True:
            tipo = input("¿Es 'ingreso' o 'gasto'? ").strip().lower()
            if tipo in ["ingreso", "gasto"]:
                break
            print("❌ Por favor ingrese 'ingreso' o 'gasto'")

        # Solicitar monto
        while True:
            monto_str = input("¿Cuál es el monto? (en soles, ej. 20.00) ").strip()
            try:
                monto = float(monto_str)
                if monto > 0:
                    break
                print("❌ El monto debe ser mayor a 0")
            except ValueError:
                print("❌ Por favor ingrese un número válido")

        # Solicitar destinatario
        destinatario = input("¿Quién es el destinatario o comercio? ").strip()
        if not destinatario:
            destinatario = "desconocido"

        # Solicitar motivo
        motivo = input("¿Cuál fue el motivo de este movimiento? ").strip()
        if not motivo:
            motivo = "Sin motivo especificado"

        print("\n" + "=" * 50)
        print("✅ Datos recopilados correctamente")
        print("=" * 50 + "\n")

        # Construir diccionario normalizado
        ahora = datetime.now()
        evento_id = str(uuid.uuid4())

        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": destinatario,
            "event_id": evento_id,
            "canal": "manual",
            "fecha_hora": ahora.isoformat(),
            "mensaje_raw": f"Entrada manual: motivo={motivo}, monto={monto}",
            "motivo": motivo,
            "fuente": "por definir",
            "origen_paquete": "manual.entry",
            "titulo_visual": "Registro Manual",
            "timestamp_epoch": time.time(),
            # Campos adicionales para SQLite
            "es_prestamo": 0,
            "monto_pagado": 0.0,
            "saldo_pendiente": monto if tipo == "gasto" else 0.0,
            "estado_prestamo": "n/a",
            "looker": 0,
            "categoria": "Manual",
        }

        return normalizado

    def _completar_datos_parciales(self, datos_parciales: dict) -> dict:
        """Completa los campos faltantes usando los datos proporcionados.

        Args:
            datos_parciales: Diccionario con algunos campos ya proporcionados
                            (puede venir de flags de CLI o parseo previo)

        Returns:
            Diccionario con todos los campos normalizados completos.
        """
        # Usar valores proporcionados o por defecto (SIN solicitar input
        # cuando ya tenemos datos del CLI o flujo automatizado)
        tipo = datos_parciales.get("tipo", "") or "ingreso"
        monto = float(datos_parciales.get("monto", 0.0) or 0.0)
        destinatario = datos_parciales.get("destinatario", "") or "desconocido"
        motivo = datos_parciales.get("motivo", "") or "Sin motivo especificado"

        # Construir diccionario normalizado
        ahora = datetime.now()
        evento_id = str(uuid.uuid4())

        normalizado = {
            "monto": monto,
            "tipo": tipo,
            "destinatario": destinatario,
            "event_id": evento_id,
            "canal": "manual",
            "fecha_hora": ahora.isoformat(),
            "mensaje_raw": f"Entrada manual: motivo={motivo} - S/ {monto}",
            "motivo": motivo,
            "fuente": "por definir",
            "origen_paquete": "manual.entry",
            "titulo_visual": "Registro Manual",
            "timestamp_epoch": time.time(),
            # Campos adicionales para SQLite
            "es_prestamo": 0,
            "monto_pagado": 0.0,
            "saldo_pendiente": monto if tipo == "gasto" else 0.0,
            "estado_prestamo": "n/a",
            "looker": 0,
            "categoria": "Manual",
        }

        return normalizado