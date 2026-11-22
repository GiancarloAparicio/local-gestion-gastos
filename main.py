#!/usr/bin/env python3
"""Punto de entrada principal del sistema local-gestion-gastos."""

import sys
import os
import argparse
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adaptadores.infraestructura.sqlite_adapter import SQLiteAdapter
from modulios.fifo_cola import FIFOCola


def main():
    # Cargar configuración desde config.yaml
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    parser = argparse.ArgumentParser(description="Sistema local-gestion-gastos")
    parser.add_argument(
        "--accion",
        choices=["listar", "sync", "insert", "fifo", "listener"],
        default="listar",
        help="Acción a realizar: listar (ver transacciones), sync (sincronizar con nube), "
             "insert (insertar manual), fifo (procesar archivos Automate), listener (capturar notificaciones directas)",
    )
    parser.add_argument(
        "--motivo",
        type=str,
        default="",
        help="Motivo del movimiento (para modo manual)",
    )
    parser.add_argument(
        "--monto",
        type=float,
        default=0.0,
        help="Monto del movimiento (para modo manual)",
    )
    parser.add_argument(
        "--tipo",
        type=str,
        default="",
        help="Tipo (ingreso/gasto) (para modo manual)",
    )
    parser.add_argument(
        "--destinatario",
        type=str,
        default="",
        help="Persona o comercio (para modo manual)",
    )
    # El directorio viene de config.yaml por defecto; --directorio solo si se quiere sobreescribir
    parser.add_argument(
        "--directorio",
        type=str,
        default=config.get('directorio_archivos_automate', '/sdcard/Automate/notify'),
        help="Directorio donde Automate deja los archivos JSON (sobreescribe config.yaml). "
             "Default leído de config.yaml: directorio_archivos_automate",
    )
    parser.add_argument(
        "--modo",
        choices=["automate_broker", "listener_directo"],
        default="automate_broker",
        help="Modo de operación: automate_broker (procesa archivos JSON de Automate) o "
             "listener_directo (captura notificaciones directas via Termux API)",
    )

    args = parser.parse_args()

    # 1. Inicializar base de datos (la conexión se mantiene abierta)
    db = SQLiteAdapter(db_ruta="local_gastos.db")

    # 2. Ejecutar según acción
    if args.accion == "listar":
        transacciones = db.listar_transacciones(limite=10, sincronizado=None)
        print(f"\n📊 Últimas {len(transacciones)} transacciones:")
        for t in transacciones:
            print(
                f"  - {t.get('fecha', 'N/A')} | "
                f"{t.get('tipo', 'N/A')} | S/ {t.get('monto_total', 0):.2f} | "
                f"{t.get('destinatario', 'N/A')}"
            )

    elif args.accion == "sync":
        print("\n🔄 Sincronizando transacciones pendientes...")
        pendientes = db.listar_transacciones(limite=100, sincronizado=0)
        print(f"📋 {len(pendientes)} transacciones pendientes de sincronizar")
        if pendientes:
            for t in pendientes[:3]:
                db.actualizar_sincronizacion(t["id_transaccion"], 1)
            print("✅ 3 transacciones marcadas como sincronizadas (demo)")
        else:
            print("✅ No hay transacciones pendientes")

    elif args.accion == "insert":
        if not args.motivo:
            print("❌ Error: Se requiere --motivo")
            sys.exit(1)
        if not args.tipo or args.tipo not in ["ingreso", "gasto"]:
            print("❌ Error: Se requiere --tipo válido")
            sys.exit(1)
        if not args.destinatario:
            print("❌ Error: Se requiere --destinatario")
            sys.exit(1)
        if args.monto <= 0:
            print("❌ Error: El monto debe ser > 0")
            sys.exit(1)

        import uuid
        from datetime import datetime

        evento_id = str(uuid.uuid4())
        ahora = datetime.now()
        db.guardar_transaccion_sql_directo(
            id_transaccion=evento_id,
            fecha_hora_epoch=ahora.timestamp(),
            fecha=ahora.strftime("%Y-%m-%d"),
            hora=ahora.strftime("%H:%M:%S"),
            trimestre=f"{ahora.year}-Q{((ahora.month - 1) // 3) + 1}",
            app="manual",
            paquete="manual.entry",
            dispositivo="CLI-Manual",
            tipo=args.tipo,
            medio="Manual",
            monto_total=args.monto,
            moneda="PEN",
            destinatario=args.destinatario,
            motivo=args.motivo,
            categoria="Manual",
            es_prestamo=0,
            monto_pagado=0.0,
            saldo_pendiente=args.monto if args.tipo == "gasto" else 0.0,
            estado_prestamo="n/a",
            looker=0,
            latitud=None,
            longitud=None,
            fuente_gps="none",
            mensaje_raw=f"Entrada manual: {args.motivo} - S/ {args.monto}",
            status="consolidado",
            sincronizado=0,
            intentos_sync=0,
            ultimo_error_sync="",
        )

        print(f"\n✅ Transacción registrada manualmente!")
        print(f"   event_id: {evento_id}")
        print(f"   Motivo: {args.motivo}")
        print(f"   Monto: S/ {args.monto:.2f}")
        print(f"   Tipo: {args.tipo}")
        print(f"   Destinatario: {args.destinatario}")
        print(f"   Sincronizado: NO (0) - Ejecute 'python3 main.py --sync' para enviar a la nube")

    elif args.accion == "fifo":
        """Procesar archivos del directorio con el modo Automate Broker."""
        directorio = args.directorio or os.getenv(
            "DIRECTORIO_NOTIFICACIONES", "/sdcard/Automate/notify"
        )
        print(f"\n🔄 Modo Automate Broker: procesando archivos de {directorio}")
        fifo = FIFOCola(directorio_monitor=directorio, modo_operacion=args.modo)
        fifo.iniciar()

    elif args.accion == "listener":
        """Capturar notificaciones directas modo listener_directo."""
        print(f"\n🔄 Modo Listener Directo: capturando notificaciones")
        directorio = args.directorio or "/tmp/termux_notifications"
        os.makedirs(directorio, exist_ok=True)
        fifo = FIFOCola(directorio_monitor=directorio, modo_operacion=args.modo)
        fifo.iniciar()

    # Ya no llamamos a db.cerrar_conexion() explícitamente;
    # Python hará cleanup al finalizar el script

    print("\n--- Fin del sistema ---")


if __name__ == "__main__":
    main()
