"""Sistema local-gestion-gastos - Punto de entrada principal."""

import sys
import os
import argparse
import sqlite3

# Logging simple y directo
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("sistema_gastos")


def get_db():
    """Obtener conexión a la base de datos SQLite."""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_gastos.db')
    conn = sqlite3.connect(db_path)
    # Los índices de columnas comprobados: 12=monto_total, 14=destinatario, 15=motivo
    conn.row_factory = sqlite3.Row
    return conn


def cmd_listar():
    """Listar últimas transacciones."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Índices comprobados: 12=monto_total, 14=destinatario, 15=motivo
        cursor.execute('SELECT monto_total, destinatario, motivo FROM transacciones ORDER BY id DESC LIMIT 10')
        rows = cursor.fetchall()
        print(f"\nÚltimas {len(rows)} transacciones:")
        for i, row in enumerate(rows, 1):
            monto = row[0] if row else 0
            destinatario = row[1] if len(row) > 1 else "N/A"
            motivo = row[2][:20] if len(row) > 2 and row[2] else "SIN MOTIVO"
            print(f"  {i}. Monto: S/ {monto:.2f} | Destinatario: {destinatario} | Motivo: {motivo}")
        conn.close()
    except Exception as e:
        logger.error(f"Error al listar: {e}")
        print(f"❌ Error al listar: {e}")


def cmd_insertar(motivo, monto, tipo, destinatario):
    """Insertar una nueva transacción manual."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Determinar tipo de transacción
        tipo_db = "gasto" if tipo and tipo.lower() in ["gasto", ""] else "ingreso"
        
        # Insertar transacción con campos correctos (índices 12=monto, 14=destinatario, 15=motivo)
        mensaje = f"Entrada manual: {motivo} - S/ {monto}"
        cursor.execute(
            "INSERT INTO transacciones (tipo, monto_total, destinatario, motivo, mensaje_raw) VALUES (?, ?, ?, ?, ?)",
            (tipo_db, float(monto), destinatario, motivo, mensaje)
        )
        conn.commit()
        
        # Obtener el ID insertado
        nuevo_id = cursor.lastrowid
        
        print(f"\n✅ Transacción registrada exitosamente!")
        print(f"   event_id: {nuevo_id}")
        print(f"   Motivo: {motivo}")
        print(f"   Monto: S/ {monto:.2f}")
        print(f"   Tipo: {tipo}")
        print(f"   Destinatario: {destinatario}")
        
        conn.close()
    except Exception as e:
        logger.error(f"❌ Error al insertar: {e}")
        print(f"❌ Error al insertar: {e}")


def main():
    print("=" * 50)
    print("SISTEMA LOCAL-GESTION-GASTOS")
    print("=" * 50)
    
    # Verificar base de datos
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM transacciones')
    total = cursor.fetchone()[0]
    print(f"📊 Total de transacciones en BD: {total}")
    conn.close()
    
    parser = argparse.ArgumentParser(description="Sistema de gestión de gastos")
    parser.add_argument(
        "--accion",
        choices=["listar", "insertar"],
        default="listar",
        help="Acción a realizar",
    )
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
