#!/usr/bin/env python3
"""Sistema local-gestion-gastos - main.py modular, leyendo config.yaml."""

import os, sys, argparse, json, datetime, time as _time, logging, importlib, yaml
from adaptadores.infraestructura.sqlite_adapter import SQLiteAdapter
from modulios.logger import info, warning, error
from modulios.termux_api import TermuxAPI
from modulios.consolidador import Consolidador

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
# --- NUEVA CONFIGURACIÓN DE TERMUX ---
TERMUX_PATH = CONFIG.get('termux', {}).get('path', '/data/data/com.termux/files/usr/bin')

# Configurar logger
logging.basicConfig(level=getattr(logging, LOG_NIVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_ARCHIVO, encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger("Main")

# ===================================================================
# FUNCIÓN 1: Obtener adapter de BD
# ===================================================================
def obtener_adapter():
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
        # Pasar la ruta de Termux desde config
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
# ===================================================================
def cargar_adaptadores():
    MODULOS = {
        "ibk": "adaptadores.ibk", "yape": "adaptadores.yape",
        "bbva": "adaptadores.bbva", "nfc": "adaptadores.nfc",
        "manual": "adaptadores.manual", "compartamos": "adaptadores.compartamos",
        "plin": "adaptadores.plin",
    }
    adaptadores = {}
    for clave, mod in MODULOS.items():
        try:
            md = importlib.import_module(mod)
            adaptadores[clave] = getattr(md, clave.capitalize() + "Adapter")
        except Exception:
            pass
    # Filtrar solo los activos en config
    return {k: v for k, v in adaptadores.items() if k in ADAPTADORES_ACTIVOS}

# ===================================================================
# FUNCIÓN: Encontrar adaptador por paquete
# ===================================================================
def encontrar_adaptador(paquete, adaptadores):
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
        for i, row in enumerate(transacciones, 1):
            monto = row.get('monto_total', 0) if row else 0
            destinatario = row.get('destinatario', 'N/A') if row else 'N/A'
            motivo = row.get('motivo', '')[:20] if row and row.get('motivo') else 'SIN MOTIVO'
            print(f"  {i}. Monto: S/ {monto:.2f} | Destinatario: {destinatario} | Motivo: {motivo}")
    except Exception as e:
        print(f"❌ Error al listar: {e}", file=sys.stderr)

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
        print(f"✅ Transacción registrada: event_id generado en BD")
    except Exception as e:
        print(f"❌ Error al insertar: {e}", file=sys.stderr)

# ===================================================================
# FUNCIÓN: Procesar notificación (pipeline automate_broker)
# ===================================================================
def procesar_notificacion(datos_crudos, adapter, adaptadores, termux_api, ventana_minutos):
    from modulios.consolidador import Consolidador
    
    # 1. Enrutar adaptador
    paquete = datos_crudos.get('packageName', '') or datos_crudos.get('package', '')
    adaptador_local = encontrar_adaptador(paquete, adaptadores)
    if not adaptador_local:
        warning("Ningún adaptador reconoció este paquete: " + paquete)
        return False
    
    # 2. Normalizar
    normalizado = adaptador_local.normalizar_notificacion(datos_crudos)
    
    # 2B. Validar duplicado (misma tipo NUNCA es duplicado)
    c = Consolidador(ventana_minutos=ventana_minutos)
    es_duplicado = c.verificar_duplicado_ventana(normalizado)
    
    if es_duplicado:
        info("🔁 Duplicado en ventana de consolidación - sin registrar nuevo")
        return False
    
    # 3. Solicitar motivo (OBLIGATORIO)
    td = TermuxAPI()
    tipo = normalizado.get('tipo', 'gasto')
    pregunta = "[%s] ¿Cuál fue el motivo de este %s? (app: %s)" % (tipo.upper(), 
        'gasto' if tipo == 'gasto' else 'ingreso', normalizado.get('origen_paquete', 'app'))
    resultado = td.mostrar_dialogo(widget="text", titulo="[%s] Motivo" % tipo.upper(), mensaje=pregunta)
    if resultado and "text" in resultado:
        motivo_usuario = resultado["text"].strip()
        normalizado['motivo'] = motivo_usuario if motivo_usuario else None
    else:
        normalizado['motivo'] = "Sin motivo especificado"
    
    # 4. GPS
    lat = obtener_gps()
    
    # 5. Insertar en SQLite
    try:
        ahora = datetime.datetime.now()
        q = _trimestre(ahora.month)
        adapter.guardar_transaccion_sql_directo(
            id_transaccion=normalizado.get('event_id') or os.urandom(12).hex(),
            fecha_hora_epoch=_time.time(),
            fecha_iso=ahora.isoformat(),
            fecha=ahora.strftime('%Y-%m-%d'),
            hora=ahora.strftime('%H:%M:%S'),
            trimestre=q, app=normalizado.get('origen_paquete', 'manual'), paquete=normalizado.get('paquete', ''),
            dispositivo=os.environ.get('ANDROID_ID', 'CLI-Manual'),
            tipo=normalizado.get('tipo', 'gasto'), medio=normalizado.get('medio', ''),
            monto_total=normalizado.get('monto', 0.0), moneda=normalizado.get('moneda', 'PEN'),
            destinatario=normalizado.get('destinatario', 'desconocido'), motivo=normalizado.get('motivo', ''),
            categoria=normalized.get('categoria', 'Manual'), es_prestamo=normalizado.get('es_prestamo', 0),
            monto_pagado=normalizado.get('monto_pagado', 0.0), saldo_pendiente=normalizado.get('saldo_pendiente', 0.0),
            estado_prestamo=normalizado.get('estado_prestamo', 'activo'), looker=normalized.get('looker', 0),
            latitud=lat[0], longitud=lat[1], fuente_gps=lat[2],
            mensaje_raw=normalizado.get('mensaje_raw', ''), status='consolidado',
            sincronizado=0, intentos_sync=0, ultimo_error_sync='')
        info("✅ Transacción registrada: event_id generado en BD")
        return True
    except Exception as e:
        error("❌ Error guardando en BD: " + str(e))
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
    if not os.path.isdir(archivo_json) and os.path.isfile(archivo_json):
        info("▶ Modo automate_broker: procesando archivo " + archivo_json)
        
        if not os.path.isfile(archivo_json):
            error("Archivo no encontrado: " + archivo_json)
            return
        
        try:
            with open(archivo_json, 'r', encoding='utf-8') as f:
                datos_crudos = json.load(f)
        except Exception as e:
            error("❌ Leyendo " + archivo_json + ": " + str(e))
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
    
    info("▶ Modo automate_broker: procesando directorio " + directorio)
    
    archivos = [f for f in os.listdir(directorio) if f.endswith('.json')]
    if not archivos:
        info("📭 No hay archivos nuevos")
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
            error("❌ Error procesando " + archivo + ": " + str(e))