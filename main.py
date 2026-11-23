#!/usr/bin/env python3
"""Sistema local-gestion-gastos - main.py modular, leyendo config.yaml."""

import os, sys, argparse, json, datetime, time as _time, logging, importlib, yaml, sqlite3
from adaptadores.infraestructura.sqlite_adapter import SQLiteAdapter
from modulios.logger import info, warning, error
from modulios.termux_api import TermuxAPI
from modulios.consolidador import Consolidador
import pprint

# ===================================================================
# CONFIGURACIÓN CENTRAL (leída de config.yaml)
# ===================================================================
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    CONFIG = yaml.safe_load(f)

BD_TIPO = CONFIG.get('bd', {}).get('tipo', 'sqlite')
BD_RUTA = CONFIG.get('bd', {}).get('ruta_sqlite', './local_gastos.db')
MODO_OPERACION = CONFIG.get('modo_operacion', 'automate_broker')
VENTANA_CONSOLIDACION = CONFIG.get('ventana_consolidacion', {}).get('minutos', 5)
TIEMPO_ESPERA_GPS = CONFIG.get('procesamiento', {}).get('tiempo_espera_gps_segundos', 10)
TIEMPO_ESPERA_DIALOGO = CONFIG.get('procesamiento', {}).get('tiempo_espera_dialogo_segundos', 30)
MAX_INTENTOS_SINCRONIZACION = CONFIG.get('procesamiento', {}).get('maximo_intentos_sincronizacion', 3)
BACKOFF_ESPERA = CONFIG.get('procesamiento', {}).get('backoff_espera_segundos', [5, 10, 30])
ADAPTADORES_ACTIVOS = CONFIG.get('adaptadores_activos', [])
MAPEO_ADAPTADORES = CONFIG.get('mapeo_adaptadores', {})
DIRECTORIO_CONF = CONFIG.get('directorio_archivos_automate', '/sdcard/storage/shared/Documents/noti.json')
LOG_NIVEL = CONFIG.get('logging', {}).get('nivel', 'INFO')
LOG_ARCHIVO = CONFIG.get('logging', {}).get('archivo', './logs/app.log')
# --- Configuración de Termux ---
TERMUX_PATH = CONFIG.get('termux', {}).get('path', '/data/data/com.termux/files/usr/bin')

# Configurar logger
logging.basicConfig(level=getattr(logging, LOG_NIVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_ARCHIVO, encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger("Main")

# ===================================================================
# FUNCIÓN 1: Obtener adapter de BD
# ===================================================================
def obtener_adapter_BD():
    db_path = BD_RUTA
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
    adapter = SQLiteAdapter(db_path)
    adapter._inicializar_bd()
    return adapter

# ===================================================================
# FUNCIÓN 2: GPS Termux (usa ruta configurada)
# ===================================================================
def obtener_gps():
    from modulios.termux_api import TermuxAPI
    try:
        termux_api = TermuxAPI(termux_path=TERMUX_PATH)
        gps_data = termux_api.obtener_gps(timeout=TIEMPO_ESPERA_GPS)
        if gps_data:
            return gps_data.get('latitud'), gps_data.get('longitud'), gps_data.get('fuente_gps', 'live')
    except Exception:
        pass
    return None, None, 'none'

# ===================================================================
# FUNCIÓN: Trimestre (pura)
# ===================================================================
def _trimestre(mes):
    if mes in [1, 2, 3]: return 'Q1'
    elif mes in [4, 5, 6]: return 'Q2'
    elif mes in [7, 8, 9]: return 'Q3'
    else: return 'Q4'

# ===================================================================
# FUNCIÓN: Cargar adaptadores dinámicamente
# Intenta varios nombres de clase para compatibilidad con convenios variados
# ===================================================================
def _nombre_clase_adaptador(clave):
    """Genera variaciones posibles de nombre de clase para un clave dada."""
    base = clave.capitalize()
    variantes = [
        base + "Adapter",       # e.g. "NfcAdapter"
        clave.upper() + "Adapter",  # e.g. "NFCAdapter"
        clave + "Adapter",      # e.g. "nfcAdapter" (aunque es raro)
    ]
    return variantes

def cargar_adaptadores():
    MODULOS = {
        "ibk": "adaptadores.ibk", 
        "yape": "adaptadores.yape",
        "bbva": "adaptadores.bbva", 
        "nfc": "adaptadores.nfc",
        "manual": "adaptadores.manual", 
        "compartamos": "adaptadores.compartamos"
    }
    adaptadores = {}
    for clave, mod in MODULOS.items():
        try:
            md = importlib.import_module(mod)
            # Probar variaciones de nombre de clase
            cls_nombre = None
            for variante in _nombre_clase_adaptador(clave):
                if hasattr(md, variante):
                    cls_nombre = variante
                    break
            if cls_nombre is None:
                # Último recurso: usar el primer atributo que termine en Adapter
                for attr in dir(md):
                    if attr.endswith("Adapter"):
                        cls_nombre = attr
                        break
            if cls_nombre:
                adaptadores[clave] = getattr(md, cls_nombre)
        except Exception:
            pass
    # Filtrar solo los activos en config
    return {k: v for k, v in adaptadores.items() if k in ADAPTADORES_ACTIVOS}

# ===================================================================
# FUNCIÓN: Encontrar adaptador por paquete
# Usa primero el mapeo de config, luego fallback a substring match
# ===================================================================
def encontrar_adaptador(paquete, adaptadores, mapeo=None):
    if mapeo is None:
        mapeo = MAPEO_ADAPTADORES  # desde config.yaml global
    # 1. Intentar matching por mapeo de paquetes (config.yaml)
    if paquete and paquete in mapeo:
        clave = mapeo[paquete]
        if clave in adaptadores:
            return adaptadores[clave]()
    # 2. Fallback: substring match simple (paquete contiene clave)
    for clave, cls in adaptadores.items():
        if paquete and clave in paquete:
            return cls()
    return None

# ===================================================================
# FUNCIÓN: Comando LISTAR (consola solo)
# ===================================================================
def cmd_listar(adapter):
    try:
        transacciones = adapter.listar_transacciones(limite=10)
        if not transacciones:
            print("📭 No hay transacciones registradas")
            return
        for i, row in enumerate(transacciones, 1):
            monto = row.get('monto_total', 0) if row else 0
            destinatario = row.get('destinatario', 'N/A') if row else 'N/A'
            motivo = row.get('motivo', '')[:20] if row and row.get('motivo') else 'SIN MOTIVO'
            print(f"  {i}. Monto: S/ {monto:.2f} | Destinatario: {destinatario} | Motivo: {motivo}")
    except Exception as e:
        print(f"❌ Error al listar: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

# ===================================================================
# FUNCIÓN: Comando INSERTAR
# ===================================================================
def cmd_insertar(motivo, monto, tipo, destinatario, adapter, adaptadores):
    try:
        ahora = datetime.datetime.now()
        q = _trimestre(ahora.month)
        adaptador = encontrar_adaptador('manual', adaptadores)
        if adaptador is None:
            import adaptadores.manual as m
            adaptador = m.ManualAdapter
        adapter.guardar_transaccion_sql_directo(
            id_transaccion=os.urandom(12).hex(),
            fecha_hora_epoch=_time.time(),
            fecha_iso=ahora.isoformat(),
            fecha=ahora.strftime('%Y-%m-%d'),
            hora=ahora.strftime('%H:%M:%S'),
            trimestre=q, app='manual', paquete='manual.entry', dispositivo='CLI-Manual',
            tipo=tipo, medio='', monto_total=monto, moneda='PEN',
            destinatario=destinatario, motivo=motivo, categoria='Manual',
            es_prestamo=0, monto_pagado=0.0, saldo_pendiente=monto,
            estado_prestamo='activo', looker=0, latitud=None, longitud=None,
            fuente_gps='none', mensaje_raw=f'{motivo} - S/ {monto}',
            status='pendiente', sincronizado=0, intentos_sync=0, ultimo_error_sync='')
        print("✅ Transacción registrada: event_id generado en BD")
    except Exception as e:
        print(f"❌ Error al insertar: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

def _resumen_estructura(obj, max_len=2000):
    """Devuelve tipo, claves/estructura y representación legible sin romper por tipos raros."""
    tipo_nombre = type(obj).__name__
    claves = list(obj.keys()) if isinstance(obj, dict) else None
    try:
        representacion = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        representacion = pprint.pformat(obj, depth=4, width=100)

    if len(representacion) > max_len:
        representacion = representacion[:max_len] + f"\n... [truncado, total {len(representacion)} chars]"

    return tipo_nombre, claves, representacion

# ===================================================================
# FUNCIÓN: Procesar notificación (pipeline automate_broker)
# ===================================================================
def procesar_notificacion(datos_crudos, adapter, adaptadores, termux_api, ventana_minutos):
    from modulios.consolidador import Consolidador

    info("📥 [PIPELINE] Iniciando procesar_notificacion")

    # 0. Inspeccionar estructura exacta de datos_crudos
    tipo_crudo, claves_crudo, repr_crudo = _resumen_estructura(datos_crudos)
    info(f"🔎 [0/5] datos_crudos | tipo={tipo_crudo} | claves={claves_crudo}")
    info(f"📄 [0/5] Contenido exacto datos_crudos:\n{repr_crudo}")

    if not isinstance(datos_crudos, dict):
        error(f"❌ [0/5] datos_crudos no es un dict (recibido {tipo_crudo}); abortando")
        return False

    # 1. Enrutar adaptador
    paquete = datos_crudos.get('packageName') or datos_crudos.get('package') or ''
    info(f"🧭 [1/5] Enrutando adaptador | paquete='{paquete}' | adaptadores_disponibles={list(adaptadores.keys())}")

    adaptador_local = encontrar_adaptador(paquete, adaptadores)
    if not adaptador_local:
        warning(f"⚠️ [1/5] Ningún adaptador reconoció el paquete: '{paquete}'")
        return False

    info(f"✅ [1/5] Adaptador seleccionado: {type(adaptador_local).__name__}")

    # 2. Normalizar
    try:
        normalizado = adaptador_local.normalizar_notificacion(datos_crudos)
    except Exception as e:
        error(f"❌ [2/5] Error en {type(adaptador_local).__name__}.normalizar_notificacion(): {e}")
        import traceback
        error(traceback.format_exc())
        return False

    tipo_norm, claves_norm, repr_norm = _resumen_estructura(normalizado)
    info(f"🔄 [2/5] Normalización completada | tipo={tipo_norm} | claves={claves_norm}")
    info(f"📦 [2/5] Estructura normalizada:\n{repr_norm}")

    if not isinstance(normalizado, dict):
        error(f"❌ [2/5] normalizar_notificacion no devolvió dict (recibido {tipo_norm})")
        return False

    # 2B. Validar duplicado (misma tipo NUNCA es duplicado)
    try:
        c = Consolidador(ventana_minutos=ventana_minutos)
        es_duplicado = c.verificar_duplicado_ventana(normalizado)
        info(f"🔍 [2B/5] Verificación duplicado (ventana={ventana_minutos} min) -> es_duplicado={es_duplicado}")
    except Exception as e:
        error(f"❌ [2B/5] Error al verificar duplicado en Consolidador: {e}")
        import traceback
        error(traceback.format_exc())
        return False

    if es_duplicado:
        info("🔁 [2B/5] Duplicado en ventana de consolidación - sin registrar nuevo")
        return False

    # 3. Solicitar motivo (OBLIGATORIO)
    api_dialogo = termux_api if termux_api is not None else TermuxAPI(termux_path=TERMUX_PATH)
    tipo = normalizado.get('tipo', 'gasto')
    origen_paq = normalizado.get('origen_paquete', 'app')
    pregunta = "[%s] ¿Cuál fue el motivo de este %s? (app: %s)" % (
        str(tipo).upper(),
        'gasto' if tipo == 'gasto' else 'ingreso',
        origen_paq
    )
    info(f"💬 [3/5] Solicitando motivo vía diálogo Termux | tipo={tipo} | app={origen_paq}")

    try:
        resultado = api_dialogo.mostrar_dialogo(
            widget="text",
            titulo="[%s] Motivo" % str(tipo).upper(),
            mensaje=pregunta
        )
        info(f"💬 [3/5] Respuesta diálogo recibida: {resultado!r}")
    except Exception as e:
        warning(f"⚠️ [3/5] Falló mostrar_dialogo ({e}); usando motivo por defecto")
        resultado = None

    if isinstance(resultado, dict) and "text" in resultado:
        motivo_usuario = str(resultado["text"]).strip()
        normalizado['motivo'] = motivo_usuario if motivo_usuario else "Sin motivo especificado"
    else:
        normalizado['motivo'] = "Sin motivo especificado"

    info(f"✍️ [3/5] Motivo asignado: '{normalizado['motivo']}'")

    # 4. GPS
    info("📍 [4/5] Obteniendo ubicación GPS...")
    lat = obtener_gps()
    info(f"📍 [4/5] Resultado GPS: lat={lat[0]}, lon={lat[1]}, fuente={lat[2]}")

    # 5. Insertar en SQLite
    event_id = normalizado.get('event_id') or os.urandom(12).hex()
    ahora = datetime.datetime.now()
    q = _trimestre(ahora.month)

    payload_bd = {
        "id_transaccion": event_id,
        "fecha_hora_epoch": _time.time(),
        "fecha_iso": ahora.isoformat(),
        "fecha": ahora.strftime('%Y-%m-%d'),
        "hora": ahora.strftime('%H:%M:%S'),
        "trimestre": q,
        "app": normalizado.get('origen_paquete', 'manual'),
        "paquete": normalizado.get('paquete', paquete),
        "dispositivo": os.environ.get('ANDROID_ID', 'CLI-Manual'),
        "tipo": normalizado.get('tipo', 'gasto'),
        "medio": normalizado.get('medio', ''),
        "monto_total": normalizado.get('monto', 0.0),
        "moneda": normalizado.get('moneda', 'PEN'),
        "destinatario": normalizado.get('destinatario', 'desconocido'),
        "motivo": normalizado.get('motivo', ''),
        "categoria": normalizado.get('categoria', 'Manual'),
        "es_prestamo": normalizado.get('es_prestamo', 0),
        "monto_pagado": normalizado.get('monto_pagado', 0.0),
        "saldo_pendiente": normalizado.get('saldo_pendiente', 0.0),
        "estado_prestamo": normalizado.get('estado_prestamo', 'activo'),
        "looker": normalizado.get('looker', 0),
        "latitud": lat[0],
        "longitud": lat[1],
        "fuente_gps": lat[2],
        "mensaje_raw": normalizado.get('mensaje_raw', ''),
        "status": 'consolidado',
        "sincronizado": 0,
        "intentos_sync": 0,
        "ultimo_error_sync": '',
    }

    info(f"💾 [5/5] Guardando en BD | id={event_id} | tipo={payload_bd['tipo']} | monto={payload_bd['monto_total']} {payload_bd['moneda']} | dest='{payload_bd['destinatario']}'")

    try:
        adapter.guardar_transaccion_sql_directo(**payload_bd)
        info(f"✅ [5/5] Transacción registrada en BD | event_id={event_id}")
        return True
    except Exception as e:
        error(f"❌ [5/5] Error guardando en BD (event_id={event_id}): {e}")
        import traceback
        error(traceback.format_exc())
        return False
    
# ===================================================================
# FUNCIÓN: Modo AUTOMATE BROKER (archivo JSON único o directorio)
# ===================================================================
def modo_automate_broker(adapter, adaptadores, archivo_json=None):
    """
    Modo automate_broker: Automate deja un archivo .json con notificación para procesar.
    
    Si se proporciona un archivo JSON, lo procesa directamente.
    Si se proporciona un directorio, procesa todos los archivos .json del directorio (modo legacy).
    Si no se proporciona nada, usa el archivo por defecto desde config.yaml.
    """
    # Determinar qué archivo/directorio procesar
    # Prioridad: --archivo-json > --directorio (legacy) > config.yaml default
    if archivo_json is None:
        archivo_json = DIRECTORIO_CONF
    
    # Modo: procesar un archivo JSON específico
    if os.path.isfile(archivo_json):
        logger.info("▶ Modo automate_broker: procesando archivo " + archivo_json)
        
        try:
            with open(archivo_json, 'r', encoding='utf-8') as f:
                datos_crudos = json.load(f)
        except Exception as e:
            logger.error("❌ Leyendo " + archivo_json + ": " + str(e))
            return
        
        procesar_notificacion(datos_crudos, adapter, adaptadores, TermuxAPI(termux_path=TERMUX_PATH), VENTANA_CONSOLIDACION)
        
        # Opcional: remover el archivo después de procesarlo
        try:
            os.remove(archivo_json)
        except Exception:
            pass
        return
    
    # Modo: directorio (legacy) - procesar todos los archivos .json
    directorio = archivo_json
    if not os.path.isdir(directorio):
        warning("Directorio no existe: " + directorio)
        return
    
    logger.info("▶ Modo automate_broker: procesando directorio " + directorio)
    
    archivos = [f for f in os.listdir(directorio) if f.endswith('.json')]
    if not archivos:
        logger.info("📭 No hay archivos nuevos")
        return
    
    termux_api = TermuxAPI(termux_path=TERMUX_PATH)
    
    for archivo in sorted(archivos):
        ruta = os.path.join(directorio, archivo)
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos_crudos = json.load(f)
            procesar_notificacion(datos_crudos, adapter, adaptadores, TermuxAPI(termux_path=TERMUX_PATH), VENTANA_CONSOLIDACION)
            # Intentar remover el archivo, pero no fallar si no se puede
            try:
                os.remove(ruta)
            except Exception:
                pass
        except Exception as e:
            logger.error("❌ Error procesando " + archivo + ": " + str(e))

# ===================================================================
# FUNCIÓN: Modo LISTENER DIRECTO
# ===================================================================
def modo_listener_directo():
    logger.info("🎧 Modo listener_directo configurado:")
    logger.info("   Modo operacional: " + MODO_OPERACION)
    logger.info("   Adaptadores: " + ", ".join(ADAPTADORES_ACTIVOS))
    logger.info("   Ventana consolidación: " + str(VENTANA_CONSOLIDACION) + " min")
    logger.info("   GPS espera: " + str(TIEMPO_ESPERA_GPS) + "s")
    logger.info("   Dialogo espera: " + str(TIEMPO_ESPERA_DIALOGO) + "s")
    logger.info("   Próximo paso: bucle while True + capturar nativa")

# ===================================================================
# FUNCIÓN: LIMITAR BASE DE DATOS
# ===================================================================
def limpiar_base_datos():
    """Limpiar/Resetear la base de datos SQLite.
    
    Elimina todas las transacciones de la base de datos,
    útil para reiniciar el estado después de pruebas.
    """
    db_path = BD_RUTA
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
    
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Contar transacciones antes de borrar
        cursor.execute("SELECT COUNT(*) FROM transacciones")
        count = cursor.fetchone()[0]
        # Borrar todas las transacciones
        cursor.execute("DELETE FROM transacciones")
        conn.commit()
        conn.close()
        info(f"🗑️ Base de datos limpiada: se removieron {count} transacciones")
    else:
        warning("⚠️ No existe base de datos para limpiar: " + db_path)

# ===================================================================
# FUNCIÓN: PUNTO DE ENTRADA
# ===================================================================
def main():
    parser = argparse.ArgumentParser(description="Sistema local-gestion-gastos", add_help=False)
    parser.add_argument("--accion", choices=["listar", "insertar", "automate_broker", "listener_directo", "limpiar"],
                        default="listar", help="Acción")
    parser.add_argument("--motivo", type=str, default="", help="Motivo")
    parser.add_argument("--monto", type=float, default=0.0, help="Monto")
    parser.add_argument("--tipo", type=str, default="gasto", help="Tipo (gasto/ingreso)")
    parser.add_argument("--destinatario", type=str, default="", help="Destinatario")
    parser.add_argument("--archivo-json", type=str, default="",
                        help="Archivo JSON a procesar (modo automate_broker)")
    parser.add_argument("--directorio", type=str, default="",
                        help="Directorio para modo legacy (procesa todos los .json)")
    parser.add_argument("--limpiar", action="store_true", default=False,
                        help="Limpiar/resetear la base de datos SQLite")
    args = parser.parse_args()
    
    # Determinar el archivo JSON a procesar:
    # Prioridad: --archivo-json > --directorio (legacy) > config.yaml default
    if args.archivo_json:
        archivo_json = args.archivo_json
    elif args.directorio:
        archivo_json = args.directorio
    else:
        # Si no se pasan argumentos, usar el default de config.yaml
        archivo_json = DIRECTORIO_CONF
    
    # Inicializaciones
    adapter_db = obtener_adapter_BD()
    adaptadores = cargar_adaptadores()
    lat = obtener_gps()
    
    if args.limpiar:
        limpiar_base_datos()
    elif args.accion == "listar":
        cmd_listar(adapter_db)
    elif args.accion == "insertar":
        cmd_insertar(args.motivo, args.monto, args.tipo, args.destinatario, adapter_db, adaptadores)
    elif args.accion == "automate_broker":
        modo_automate_broker(adapter_db, adaptadores, archivo_json)
    elif args.accion == "listener_directo":
        modo_listener_directo()

if __name__ == "__main__": main()