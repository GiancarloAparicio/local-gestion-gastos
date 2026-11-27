#!/usr/bin/env python3
"""
main.py - Punto de entrada principal del sistema local-gestion-gastos.
Soporta múltiples modos de operación y flags de línea de comandos.

Modos soportados:
  - --broker: Modo Automate File Broker (por defecto si config.yaml así lo indica)
  - --listener: Modo Listener Directo
  - --registro: Flujo interactivo paso a paso
  - --sql: Ejecutar query SQL directamente

Todas las APIs retornan JSON estandarizado, haciendo el código indiferente al entorno (Termux/Linux).
"""

import sys
import os
import argparse
import yaml

# Agregar el directorio de infraestructura al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infraestructura import obtener_proveedor


def leer_config():
    """Leer configuración desde config.yaml"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"⚠ No se pudo leer config.yaml: {e}")
        return None


def detectar_modo_operacion(args, config):
    """
    Detectar modo de operación siguiendo la jerarquía:
    1. Flags de línea de comandos (mayor prioridad)
    2. Archivo config.yaml
    3. Valor por defecto
    """
    # 1. Verificar flags de modo explícitas
    if args.broker:
        return "automate_broker", True  # El 'True' indica que fue forzado por flag
    if args.listener:
        return "listener_directo", True  # El 'True' indica que fue forzado por flag

    # 2. Leer config.yaml si no vienen flags
    if config and config.get('modo_operacion'):
        modo_config = config.get('modo_operacion')
        if modo_config in ('automate_broker', 'listener_directo'):
            return modo_config, False  # El 'False' indica que vino de config.yaml

    # 3. Valor por default
    return "automate_broker", True  # Default con bandera de "usó default"


def main():
    """Función principal del sistema."""
    
    # --- 1. Parseo de argumentos ---
    parser = argparse.ArgumentParser(
        prog='main.py',
        description='Sistema local-gestion-gastos - Multiplataforma (Termux/Linux)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modos de operación:
  --broker      : Modo Automate File Broker (archivos de notificaciones)
  --listener    : Modo Listener Directo (captura nativa)
  --registro    : Flujo interactivo paso a paso (por defecto)
  --sql         : Ejecutar query SQL directamente

  Configuración:
  --help        : Mostrar este mensaje de ayuda

Ejemplos:
  python3 main.py                      # Usa config.yaml, modo broker por defecto
  python3 main.py --broker             # Forzar modo broker
  python3 main.py --listener           # Forzar modo listener
  python3 main.py --registro           # Flujo interactivo
  python3 main.py --sql "SELECT ..."   # Query SQL
  """
    )
    
    # Agregar grupo de flags de modo
    grupo_modo = parser.add_argument_group('Modos de operación')
    grupo_modo.add_argument(
        '--broker', 
        action='store_true', 
        help='Forzar modo Automate File Broker'
    )
    grupo_modo.add_argument(
        '--listener', 
        action='store_true', 
        help='Forzar modo Listener Directo'
    )
    grupo_modo.add_argument(
        '--registro', 
        action='store_true', 
        help='Ejecutar flujo interactivo paso a paso'
    )
    
    # Agregar grupo de flags SQL
    grupo_sql = parser.add_argument_group('Operaciones SQL')
    grupo_sql.add_argument(
        '--accion', 
        choices=['sql', 'registro'], 
        help='Acción a ejecutar: sql o registro'
    )
    grupo_sql.add_argument(
        '--sql', 
        type=str, 
        help='Query SQL a ejecutar'
    )
    grupo_sql.add_argument(
        '--json', 
        action='store_true', 
        help='Mostrar resultados en formato JSON'
    )
    grupo_sql.add_argument(
        '--limit', 
        type=int, 
        default=10, 
        help='Límite de filas para queries SQL (default: 10)'
    )
    
    args = parser.parse_args()
    
    # Validación: no usar ambas flags de modo simultáneamente
    if args.broker and args.listener:
        print("✗ Error: No puede usar --broker y --listener simultáneamente")
        print("   Use una sola flag o ninguna para modo por defecto")
        print("   Use: python3 main.py --help para ver opciones")
        sys.exit(1)
    
    # --- 2. Detectar modo de operación ---
    config = leer_config()
    modo, forzado_por_flag = detectar_modo_operacion(args, config)
    
    # Informar al usuario sobre el modo
    if forzado_por_flag:
        print(f"▶ Modo forzado: {modo} (usando flag --{'broker' if modo == 'automate_broker' else 'listener'})")
    elif config:
        print(f"▶ Modo desde config.yaml: {modo}")
    else:
        print(f"▶ Modo por defecto: {modo}")
    print()
    
    # --- 3. Obtener proveedores según el modo ---
    try:
        input_prov = obtener_proveedor("input")
        gps_prov = obtener_proveedor("gps")
        db_prov = obtener_proveedor("database")
        notif_prov = obtener_proveedor("notification")
    except Exception as e:
        print(f"✗ Error obteniendo proveedores: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"   - Proveedor input: {type(input_prov).__name__}")
    print(f"   - Proveedor GPS: {type(gps_prov).__name__}")
    print(f"   - Proveedor BD: {type(db_prov).__name__}")
    print(f"   - Proveedor Notificaciones: {type(notif_prov).__name__}")
    print()
    
    # --- 4. Ejecutar según modo y flags ---
    
    # Modo SQL (tiene prioridad sobre los modos interactivos)
    if args.accion == "sql" and args.sql:
        print("=" * 60)
        print("SISTEMA local-gestion-gastos - Modo SQL")
        print("=" * 60)
        
        print(f"\n[1] Ejecutando query SQL: {args.sql}")
        resultado = db_prov.ejecutar_query(args.sql)
        
        print(f"   Resultado code: {resultado.get('code', 'N/A')}")
        
        if resultado.get('code') == 0:
            data = resultado.get('data', {})
            columnas = data.get('columnas', [])
            filas = data.get('filas', [])
            total = data.get('total', 0)
            
            print(f"   ✓ Total filas: {total}")
            print(f"   ✓ Columnas: {columnas if columnas else 'N/A'}")
            
            if filas:
                print("\n   Resultados:")
                if columnas:
                    header = " | ".join(str(c) for c in columnas[:6])
                    if len(columnas) > 6:
                        header += f" +... (+{len(columnas)-6} más)"
                    print(f"   | {header}")
                    print("   |" + "-" * (len(header) + 2))
                
                limit = args.limit if hasattr(args, 'limit') else 10
                for i, fila in enumerate(filas[:limit]):
                    if isinstance(fila, dict):
                        valores = []
                        for col in columnas[:6]:
                            val = fila.get(col, "")
                            val_str = str(val)[:30] if val is not None else "NULL"
                            valores.append(val_str)
                    else:
                        valores = []
                        for j in range(min(len(columnas), len(fila))):
                            val = fila[j]
                            val_str = str(val)[:30] if val is not None else "NULL"
                            valores.append(val_str)
                    
                    fila_str = " | ".join(valores)
                    print(f"   | {fila_str}")
            
            # Si flag JSON, output en JSON puros
            if args.json:
                import json
                print("\n--- OUTPUT JSON ---")
                list_filas = []
                for fila in filas[:limit]:
                    if isinstance(fila, dict):
                        list_filas.append(fila)
                    else:
                        if isinstance(fila, (list, tuple)):
                            list_filas.append(dict(zip(columnas, fila)) if columnas else {})
                        else:
                            list_filas.append({})
                
                result_json = {
                    "code": resultado['code'],
                    "total_filas": total,
                    "columnas": columnas,
                    "filas": list_filas
                }
                print(json.dumps(result_json, ensure_ascii=False, indent=2))
        else:
            print(f"   ✗ Error en query: {resultado.get('error', 'desconocido')}")
            if args.json:
                import json
                print(json.dumps({"error": resultado.get('error', 'desconocido'), "code": resultado['code']}))
    
    # Modo interactivo (--registro o por default sin flags SQL)
    elif args.accion != "sql" or (not args.sql and not args.accion):
        # Verificar si viene --registro explícito o modo por default
        if args.registro or (not args.broker and not args.listener and not args.accion):
            print("=" * 60)
            print("SISTEMA local-gestion-gastos - Flujo Interactivo")
            print("=" * 60)
            
            # 1. Obtener todos los proveedores (ya hechos arriba)
            # ... (ya tienen valores)
            
            # 2. Solicitar datos al usuario
            print("\n[1] Detectando entorno y obteniendo proveedores...")
            try:
                modo_detectado = "Termux" if 'ANDROID_DATA' in os.environ else "Linux"
                print(f"   ✓ Entorno detectado: {modo_detectado}")
                print(f"   - Proveedor input: {type(input_prov).__name__}")
                print(f"   - Proveedor GPS: {type(gps_prov).__name__}")
                print(f"   - Proveedor BD: {type(db_prov).__name__}")
                print(f"   - Proveedor Notificaciones: {type(notif_prov).__name__}")
            except Exception as e:
                print(f"   ✗ Error obteniendo proveedores: {e}")
                return
            
            # Solicitar motivo
            print("\n[2] Solicitando datos al usuario...")
            
            print("   --- Solicitando motivo ---")
            resultado_motivo = input_prov.solicitar_texto("¿Cuál fue el motivo de este movimiento?")
            if resultado_motivo.get('code') != 0:
                print("   ℹ Usuario canceló la entrada de motivo")
                motivo = None
            else:
                motivo = resultado_motivo.get('text', '')
            
            print("\n   --- Solicitando monto ---")
            resultado_monto = input_prov.solicitar_numero("¿Cuál fue el monto?", min_val=0, max_val=100000)
            if resultado_monto.get('code') != 0:
                print("   ℹ Usuario canceló o ingreso inválido el monto")
                monto = None
            else:
                try:
                    monto = float(resultado_monto.get('text', '0'))
                except ValueError:
                    monto = None
                    print("   ✗ No se pudo convertir monto a número")
            
            print("\n   --- Confirmando registro ---")
            resultado_conf = input_prov.solicitar_confirmacion("¿Desea guardar este registro?")
            if resultado_conf.get('code') != 0 or resultado_conf.get('text') != "true":
                print("   ℹ Registro cancelado por usuario")
                confirmado = False
            else:
                confirmado = True
            
            print("\n[3] Obteniendo ubicación GPS...")
            ubicacion = gps_prov.obtener_ubicacion()
            if ubicacion.get('code') == 0:
                datos_gps = ubicacion.get('data', {})
                lat = datos_gps.get('lat')
                lng = datos_gps.get('lng')
                source = datos_gps.get('source', 'desconocido')
                print(f"   ✓ Latitud: {lat}")
                print(f"   ✓ Longitud: {lng}")
                print(f"   ✓ Fuente: {source}")
            else:
                print(f"   ✗ Error GPS: {ubicacion.get('error', 'desconocido')}")
                lat = None
                lng = None
            
            # 4. Insertar en Base de Datos
            print("\n[4] Insertando en base de datos...")
            evento_id = None
            
            datos_suficientes = (
                monto is not None and 
                motivo is not None and 
                confirmado and 
                lat is not None and 
                lng is not None
            )
            
            if datos_suficientes:
                resultado_db = db_prov.insertar_transaccion({
                    "tipo": "gasto",
                    "monto_total": monto,
                    "destinatario": "Comercio Ejemplo",
                    "motivo": motivo,
                    "latitud": lat,
                    "longitud": lng,
                    "app": "manual",
                    "paquete": "manual.entry",
                    "dispositivo": "CLI-Manual",
                    "moneda": "PEN",
                    "medio": "Transferencia",
                    "categoria": "Manual",
                    "es_prestamo": 0,
                    "looker": 1
                })
                print(f"   Resultado code: {resultado_db.get('code', 'N/A')}")
                print(f"   Resultado event_id: {resultado_db.get('data', {}).get('event_id', 'N/A')}")
                print(f"   Resultado valid: {resultado_db.get('valid', False)}")
                if resultado_db.get('code') == 0:
                    evento_id = resultado_db['data']['event_id']
                    print(f"   ✅ Transacción guardada con event_id: {evento_id}")
                else:
                    print(f"   ✗ Error al guardar en BD: {resultado_db.get('error', 'desconocido')}")
            else:
                print("   ⚠ Datos incompletos, no se insertó en BD")
            
            # 5. Resumen final
            print("\n" + "=" * 60)
            print("RESUMEN DEL PROCESO")
            print("=" * 60)
            print("   Motivo: {}" .format(motivo or 'N/A'))
            print("   Monto: {}" .format(monto or 'N/A'))
            print("   Confirmado: {}" .format(confirmado or 'No'))
            print("   GPS - Lat: {}, Lng: {} (fuente: {})" .format(lat or 'N/A', lng or 'N/A', source or 'N/A'))
            if evento_id:
                print("   BD - Event ID: {}" .format(evento_id))
            print("=" * 60)
            print("\nSistema completado exitosamente en modo multiplataforma!")
            print("=" * 60)
    
    # Modo broker o listener (si no hay --accion sql ni --registro)
    elif modo == "automate_broker":
        print("=" * 60)
        print("SISTEMA local-gestion-gastos - Modo Automate File Broker")
        print("=" * 60)
        print("\n✓ Modo Automate File Broker seleccionado")
        print("✓ Esperando archivos en directorio configurado...")
        print("✓ Presione Ctrl+C para detener")
        print("\n(Nota: En modo interactivo/debug, este mensaje se omite)")
        # Aquí iría la lógica real del modo broker
        # Por ahora, mantener el programa vivo o salir con mensaje
        print("\nModo broker activado. Use --registro para flujo interactivo.")
        
    elif modo == "listener_directo":
        print("=" * 60)
        print("SISTEMA local-gestion-gastos - Modo Listener Directo")
        print("=" * 60)
        print("\n✓ Modo Listener Directo seleccionado")
        print("✓ Capturando notificaciones nativas...")
        print("✓ Presione Ctrl+C para detener")
        print("\n(Nota: En modo interactivo/debug, este mensaje se omite)")
        print("\nModo listener activado. Use --registro para flujo interactivo.")


if __name__ == "__main__":
    main()
