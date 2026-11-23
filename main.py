import os
import argparse
import sqlite3

from modulios.logger import info, warning, error, setup_logger

# Configuración inicial - el logger ya está configurado en modulios.logger
# usando la ruta de archivo desde config.yaml (./logs/app.log)

def _crear_tabla_si_no_existe():
    """Crea la tabla transacciones si no existe, con la estructura completa."""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_gastos.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_transaccion TEXT UNIQUE,
            fecha_hora_epoch REAL,
            fecha_iso TEXT,
            fecha TEXT,
            hora TEXT,
            trimestre TEXT,
            app TEXT,
            paquete TEXT,
            dispositivo TEXT,
            tipo TEXT,
            medio TEXT,
            monto_total REAL,
            moneda TEXT,
            destinatario TEXT,
            motivo TEXT,
            categoria TEXT,
            es_prestamo INTEGER,
            monto_pagado REAL,
            saldo_pendiente REAL,
            estado_prestamo TEXT,
            looker INTEGER,
            latitud REAL,
            longitud REAL,
            fuente_gps TEXT,
            mensaje_raw TEXT,
            status TEXT,
            sincronizado INTEGER,
            intentos_sync INTEGER,
            ultimo_error_sync TEXT
        )
    ''')
    conn.commit()
    conn.close()
    info("✅ Base de datos verificada/creada")

def get_db():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_gastos.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def cmd_listar():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT monto_total, destinatario, motivo FROM transacciones ORDER BY id DESC LIMIT 10')
        rows = cursor.fetchall()
        info(f"\nÚltimas {len(rows)} transacciones:")
        for i, row in enumerate(rows, 1):
            monto = row[0] if len(row) > 0 else 0
            destinatario = row[1] if len(row) > 1 else "N/A"
            motivo = row[2][:20] if len(row) > 2 and row[2] else "SIN MOTIVO"
            print(f"  {i}. Monto: S/ {monto:.2f} | Destinatario: {destinatario} | Motivo: {motivo}")
        conn.close()
    except Exception as e:
        error(f"❌ Error al listar: {e}")

def cmd_insertar(motivo, monto, tipo, destinatario):
    try:
        conn = get_db()
        cursor = conn.cursor()
        tipo_db = "gasto" if tipo and tipo.lower() in ["gasto", ""] else "ingreso"
        mensaje = f"Entrada manual: {motivo} - S/ {monto}"
        cursor.execute(
            "INSERT INTO transacciones (tipo, monto_total, destinatario, motivo, mensaje_raw) VALUES (?, ?, ?, ?, ?)",
            (tipo_db, float(monto), destinatario, motivo, mensaje)
        )
        conn.commit()
        nuevo_id = cursor.lastrowid
        info(f"✅ Transacción registrada exitosamente!")
        info(f"   event_id: {nuevo_id}")
        info(f"   Motivo: {motivo}")
        info(f"   Monto: S/ {monto:.2f}")
        info(f"   Tipo: {tipo}")
        info(f"   Destinatario: {destinatario}")
        conn.close()
    except Exception as e:
        error(f"❌ Error al insertar: {e}")

def main():
    print("=" * 50)
    print("SISTEMA LOCAL-GESTION-GASTOS")
    print("=" * 50)
    _crear_tabla_si_no_existe()
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_gastos.db'))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM transacciones')
    total = cursor.fetchone()[0]
    conn.close()
    info(f"📊 Total de transacciones en BD: {total}")
    parser = argparse.ArgumentParser(description="Sistema de gestión de gastos")
    parser.add_argument("--accion", choices=["listar", "insertar"], default="listar", help="Acción a realizar")
    parser.add_argument("--motivo", type=str, default="", help="Motivo")
    parser.add_argument("--monto", type=float, default=0.0, help="Monto")
    parser.add_argument("--tipo", type=str, default="gasto", help="Tipo (gasto/ingreso)")
    parser.add_argument("--destinatario", type=str, default="", help="Destinatario")
    args = parser.parse_args()
    if args.accion == "listar":
        cmd_listar()
    elif args.accion == "insertar":
        cmd_insertar(args.motivo, args.monto, args.tipo, args.destinatario)
    info("\n--- Fin del sistema ---")

if __name__ == "__main__":
    main()
