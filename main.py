import os
import argparse
import sqlite3

# Ruta del log usando el directorio home para que funcione en cualquier entorno
LOG_FILE = os.path.join(os.path.expanduser('~'), '.local_gestion_gastos', 'app.log')

def log_info(mensaje):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            import datetime
            f.write(f"{os.pactime.strftime('%Y-%m-%d %H:%M:%S', __import__('time').localtime())} - INFO - {mensaje}\n")
        print(f"INFO: {mensaje}")
    except Exception as e:
        print(f"ERROR de logging: {e}")

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
        print(f"\nÚltimas {len(rows)} transacciones:")
        for i, row in enumerate(rows, 1):
            monto = row[0] if len(row) > 0 else 0
            destinatario = row[1] if len(row) > 1 else "N/A"
            motivo = row[2][:20] if len(row) > 2 and row[2] else "SIN MOTIVO"
            print(f"  {i}. Monto: S/ {monto:.2f} | Destinatario: {destinatario} | Motivo: {motivo}")
        conn.close()
    except Exception as e:
        print(f"❌ Error al listar: {e}")

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
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"evento_id={nuevo_id}|motivo={motivo}|monto={monto:.2f}|tipo={tipo}\n")
        print(f"✅ Transacción registrada exitosamente!")
        print(f"   event_id: {nuevo_id}")
        print(f"   Motivo: {motivo}")
        print(f"   Monto: S/ {monto:.2f}")
        print(f"   Tipo: {tipo}")
        print(f"   Destinatario: {destinatario}")
        conn.close()
    except Exception as e:
        print(f"❌ Error al insertar: {e}")

def main():
    print("=" * 50)
    print("SISTEMA LOCAL-GESTION-GASTOS")
    print("=" * 50)
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_gastos.db'))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM transacciones')
    total = cursor.fetchone()[0]
    conn.close()
    print(f"📊 Total de transacciones en BD: {total}")
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
    print("\n--- Fin del sistema ---")

if __name__ == "__main__":
    main()
