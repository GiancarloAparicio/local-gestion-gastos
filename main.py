#!/usr/bin/env python3
"""Punto de entrada del sistema local-gestion-gastos.

Modos de operación (daemon):
  --broker     Fuerza modo Automate File Broker
  --listener   Fuerza modo Listener Directo (solo Termux)

Acciones de una sola ejecución:
  --accion listar    Lista transacciones
  --accion insertar  Inserta una transacción (flags o interactivo)
  --accion sql       Ejecuta una consulta SQL (--sql "...")
  --accion sync      Marca las transacciones pendientes como sincronizadas
  --accion registro  Flujo interactivo de registro

Sin flags: usa el modo indicado en config.yaml (modo_operacion).
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infraestructura import config, obtener_proveedor


# ---------------------------------------------------------------------------
# Utilidades de presentación
# ---------------------------------------------------------------------------
def imprimir_filas(resultado: dict, limite: int = 10, como_json: bool = False):
    """Imprime un resultado de BD en tabla o JSON."""
    if resultado.get("code") != 0:
        print(f"✗ Error: {resultado.get('error')}")
        if como_json:
            print(json.dumps({"error": resultado.get("error")}, ensure_ascii=False))
        return

    data = resultado.get("data", {})

    # Sentencias DML (INSERT/UPDATE/DELETE) no tienen filas, sólo "afectadas"
    if "afectadas" in data and "columnas" not in data:
        if como_json:
            print(json.dumps({"code": 0, "afectadas": data["afectadas"]}, ensure_ascii=False))
        else:
            print(f"✅ Filas afectadas: {data['afectadas']}")
        return

    columnas = data.get("columnas", [])
    filas = data.get("filas", [])
    total = data.get("total", len(filas))

    if como_json:
        print(json.dumps(
            {
                "code": 0,
                "total": total,
                "columnas": columnas,
                "filas": filas[:limite],
            },
            ensure_ascii=False,
            indent=2,
        ))
        return

    print(f"Total: {total} fila(s)")
    if not filas:
        print("(sin resultados)")
        return
    if columnas:
        print(" | ".join(str(c) for c in columnas))
        print("-" * 60)
    for fila in filas[:limite]:
        if isinstance(fila, dict):
            print(" | ".join("" if fila.get(c) is None else str(fila.get(c)) for c in columnas))
        else:
            print(" | ".join("" if v is None else str(v) for v in fila))


# ---------------------------------------------------------------------------
# Resolución de modo
# ---------------------------------------------------------------------------
def resolver_modo(args) -> tuple[str, str]:
    """Retorna (modo, origen) aplicando flags > config.yaml > default."""
    if args.broker:
        return "automate_broker", "flag --broker"
    if args.listener:
        return "listener_directo", "flag --listener"
    return config.modo_operacion(), "config.yaml"


# ---------------------------------------------------------------------------
# Acciones de una sola ejecución
# ---------------------------------------------------------------------------
def accion_registro(input_prov, gps_prov, db_prov) -> bool:
    """Flujo interactivo de registro. Retorna True si guardó."""
    print("=== Registro interactivo ===")

    r_motivo = input_prov.solicitar_texto("¿Cuál fue el motivo del movimiento?")
    if r_motivo.get("code") != 0 or not r_motivo.get("text"):
        print("ℹ Registro cancelado (motivo vacío).")
        return False
    motivo = r_motivo["text"]

    r_monto = input_prov.solicitar_numero("¿Cuál fue el monto?", min_val=0.01, max_val=1_000_000)
    if r_monto.get("code") != 0:
        print("✗ Monto inválido. Registro cancelado.")
        return False
    monto = float(r_monto["text"])

    r_dest = input_prov.solicitar_texto("¿Persona o comercio? (opcional)")
    destinatario = r_dest.get("text") if r_dest.get("code") == 0 and r_dest.get("text") else "manual"

    r_conf = input_prov.solicitar_confirmacion("¿Guardar este registro?")
    if r_conf.get("code") != 0 or r_conf.get("text") != "true":
        print("ℹ Registro cancelado por el usuario.")
        return False

    # GPS (opcional; si falla se guarda con fuente_gps = none)
    gps = gps_prov.obtener_ubicacion()
    if gps.get("code") == 0:
        lat = gps["data"].get("lat")
        lng = gps["data"].get("lng")
        fuente = gps["data"].get("source", "none")
        print(f"✓ GPS: {lat}, {lng} ({fuente})")
    else:
        lat = lng = None
        fuente = "none"
        print(f"ℹ GPS no disponible: {gps.get('error')}")

    db_prov.inicializar()
    resultado = db_prov.insertar_transaccion(
        {
            "tipo": "gasto",
            "monto_total": monto,
            "destinatario": destinatario,
            "motivo": motivo,
            "latitud": lat,
            "longitud": lng,
            "fuente_gps": fuente,
            "app": "manual",
            "paquete": "manual.entry",
            "dispositivo": "CLI-Manual",
            "medio": "Transferencia",
            "categoria": "Manual",
        }
    )
    if resultado.get("code") == 0:
        print(f"✅ Guardado. event_id: {resultado['data']['event_id']}")
        return True
    print(f"✗ No se pudo guardar: {resultado.get('error')}")
    return False


def accion_insertar(args, input_prov, db_prov) -> bool:
    """Inserta desde flags; si faltan datos usa entrada interactiva."""
    monto = args.monto
    motivo = args.motivo
    tipo = args.tipo or "gasto"
    destinatario = args.destinatario or "manual"

    if monto is None:
        r = input_prov.solicitar_numero("¿Monto?", min_val=0.01, max_val=1_000_000)
        if r.get("code") != 0:
            print("✗ Monto inválido.")
            return False
        monto = float(r["text"])

    if not motivo:
        r = input_prov.solicitar_texto("¿Motivo?")
        if r.get("code") != 0 or not r.get("text"):
            print("✗ Motivo requerido.")
            return False
        motivo = r["text"]

    db_prov.inicializar()
    resultado = db_prov.insertar_transaccion(
        {
            "tipo": tipo,
            "monto_total": monto,
            "motivo": motivo,
            "destinatario": destinatario,
            "app": "manual",
            "paquete": "manual.entry",
            "dispositivo": "CLI-Manual",
            "medio": "Transferencia",
            "categoria": "Manual",
        }
    )
    if resultado.get("code") == 0:
        print(f"✅ Insertado. event_id: {resultado['data']['event_id']}")
        return True
    print(f"✗ Error: {resultado.get('error')}")
    return False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Sistema local-gestion-gastos (Termux/Linux)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python3 main.py                      # modo desde config.yaml\n"
            "  python3 main.py --broker --once      # procesa archivos y sale\n"
            "  python3 main.py --listener           # solo Termux\n"
            "  python3 main.py --accion listar --json\n"
            "  python3 main.py --accion insertar --motivo pan --monto 20 --tipo gasto\n"
            "  python3 main.py --accion sql --sql \"SELECT * FROM transacciones LIMIT 5\"\n"
            "  python3 main.py --accion sync\n"
        ),
    )

    modos = parser.add_argument_group("Modos de operación")
    modos.add_argument("--broker", action="store_true", help="Forzar modo broker")
    modos.add_argument("--listener", action="store_true",
                       help="Forzar modo listener (solo Termux)")
    modos.add_argument("--once", action="store_true",
                       help="Procesar un solo ciclo y salir (modo daemon)")

    acciones = parser.add_argument_group("Acciones")
    acciones.add_argument("--accion",
                          choices=["listar", "insertar", "sql", "sync", "registro"],
                          help="Acción de una sola ejecución")
    acciones.add_argument("--registro", action="store_true",
                          help="Alias de --accion registro")
    acciones.add_argument("--sql", type=str, help="Consulta SQL a ejecutar")
    acciones.add_argument("--json", action="store_true", help="Salida en JSON")
    acciones.add_argument("--limit", type=int, default=10, help="Límite de filas")

    datos = parser.add_argument_group("Datos para insertar")
    datos.add_argument("--motivo", type=str, help="Motivo del movimiento")
    datos.add_argument("--monto", type=float, help="Monto del movimiento")
    datos.add_argument("--tipo", choices=["gasto", "ingreso"], help="Tipo de movimiento")
    datos.add_argument("--destinatario", type=str, help="Persona o comercio")

    return parser


def main():
    parser = construir_parser()
    args = parser.parse_args()

    # Validaciones de flags
    if args.broker and args.listener:
        parser.error("use --broker o --listener, no ambos")

    if args.listener and not config.es_termux():
        print("✗ --listener solo está disponible en Termux (Android).")
        print("  En Linux use --broker o --accion registro.")
        sys.exit(1)

    # Proveedores (todos comparten el mismo contrato)
    input_prov = obtener_proveedor("input")
    gps_prov = obtener_proveedor("gps")
    db_prov = obtener_proveedor("database")

    # --- Acciones de una sola ejecución ---
    accion = args.accion
    if args.registro and accion is None:
        accion = "registro"

    if accion == "sql":
        if not args.sql:
            parser.error("--accion sql requiere --sql \"...\"")
        db_prov.inicializar()
        imprimir_filas(db_prov.ejecutar_query(args.sql), args.limit, args.json)
        # Ayuda: sin ORDER BY, SQLite devuelve las filas más antiguas.
        consulta = args.sql.upper()
        if (
            not args.json
            and consulta.lstrip().startswith("SELECT")
            and "ORDER BY" not in consulta
        ):
            print(
                "\nℹ Nota: sin ORDER BY se muestran las filas más antiguas.\n"
                "  Para ver las más recientes: --accion listar, o agregue "
                "\"ORDER BY id DESC\" a su consulta."
            )
        return

    if accion == "listar":
        db_prov.inicializar()
        imprimir_filas(db_prov.listar_transacciones(args.limit), args.limit, args.json)
        return

    if accion == "insertar":
        accion_insertar(args, input_prov, db_prov)
        return

    if accion == "sync":
        db_prov.inicializar()
        resultado = db_prov.marcar_pendientes_sincronizadas()
        if resultado.get("code") == 0:
            print(f"✅ Sincronizadas: {resultado['data']['afectadas']} transacción(es)")
        else:
            print(f"✗ Error: {resultado.get('error')}")
        return

    if accion == "registro":
        accion_registro(input_prov, gps_prov, db_prov)
        return

    # --- Modo daemon (sin acción) ---
    modo, origen = resolver_modo(args)
    print(f"▶ Modo: {modo} (origen: {origen})")
    print(f"  Proveedores: input={type(input_prov).__name__}, "
          f"gps={type(gps_prov).__name__}, bd={type(db_prov).__name__}")
    print("  (Ctrl+C para detener. Registro manual: --accion registro)")

    if modo == "listener_directo" and not config.es_termux():
        print("✗ El modo listener_directo configurado requiere Termux.")
        print("  Cambie config.yaml a automate_broker o ejecute --broker.")
        sys.exit(1)

    from modulios.fifo_cola import FIFOCola

    fifo = FIFOCola(modo_operacion=modo)
    fifo.iniciar(una_vez=args.once)


if __name__ == "__main__":
    main()
