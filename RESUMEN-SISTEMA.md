# local-gestion-gastos - Documentación del Sistema

## Visión General
Sistema de gestión de gastos e ingresos para Android/Termux que procesa notificaciones de:
- **TRAN** (Transferencias bancarias)
- **PLIN** (Pagos P2P)
- **TARJETA** (Consumos con tarjeta)
- **NFC** (Google Pay / Wallet)

## Arquitectura del Sistema

### 1. Adaptadores Principales

#### adaptadores/ibk.py (505 líneas)
- Clasifica 4 formatos: TRAN, PLIN, TARJETA, NFC
- Regla fundamental: **Mismo tipo NUNCA es duplicado**
- Tipos diferentes SÍ consolidan (consolidan si mismo destinatario + monto similar + ventana 5 min)
- Siempre se solicita motivo via termux-dialog
- Monto solo se solicita para formato TARJETA (viene vacío en mensaje)
- Logging paso a paso en main.py

#### adaptadores/nfc.py (136 líneas)
- Detecta formato NFC (walletnfcrel)
- Extrae monto, beneficiario, tipo_consumo
- Solicita motivo via termux_api.solicitar_motivo_contexto
- Genera diccionario normalizado con campos NFC

### 2. Módulos Centrales

#### modulios/termux_api.py (385 líneas)
- GPS con fallback a base de datos SQLite
- `obtener_gps(timeout=15)`: GPS en tiempo real o fallback a BD
- `mostrar_dialogo(widget, titulo, mensaje)`: Diálogos Termux
- `solicitar_motivo_contexto(es_gasto, titulo_notificacion, app_nombre)`: Motivocon contexto

#### modulios/fifo_cola.py (351 líneas)
- `FIFOCola` con modos `automate_broker` y `listener_directo`
- Selección automática de adaptador por paquete de notificación
- `pe.com.interbank.mobilebanking` → IBKAdapter
- `com.google.android.apps.walletnfcrel` → NFCAdapter

#### modulios/consolidador.py y modulios/validador.py
- Validación de datos y consolidación de transacciones

### 3. Configuración

#### config.yaml
- Modo de operación: `automate_broker` o `listener_directo`
- Adaptadores activos: yape, ibk (más nfc, compartamos cuando se habiliten)
- Mapeo de paquetes a adaptadores
- Ventana de consolidación: 5 minutos
- Tiempos de espera: GPS (10s), diálogo (30s)

#### requirements.txt
```yaml
pyyaml >= 6.0
```
*(Los demás módulos son Python estándar o archivos locales)*

### 3. Estructura de Directorios
```text
local-gestion-gastos/
├── main.py                  # CLI principal
├── instalacion.sh           # Script de instalación
├── requirements.txt         # Dependencias
├── config.yaml              # Configuración del sistema
├── adaptadores/
│   ├── ibk.py (505 l)
│   ├── nfc.py (136 l)
│   ├── bbva.py, compartamos.py, manual.py, yape.py
├── modulios/
│   ├── termux_api.py (385 l)
│   ├── logger.py            - Logging centralizado
│   ├── consolidador.py, validador.py, fifo_cola.py
├── logs/                    # Archivos de log generados
├── .venv/                   # Entorno virtual Python
└── .local_gestion_gastos/   # Directorio de logs de usuario
    └── app.log
```

## Reglas de Duplicados (NUEVO)

| Combinación | ¿Duplicado? | Comportamiento |
|-------------|-------------|----------------|
| **TRAN + TRAN** | ❌ **NUNCA** | Mismo tipo = gastos distintos |
| **PLIN + PLIN** | ❌ **NUNCA** | Mismo tipo = eventos independientes |
| **TARJETA + TARJETA** | ❌ **NUNCA** | Mismo tipo = consumos distintos |
| **NFC + NFC** | ❌ **NUNCA** | Mismo tipo = pagos independientes |
| **TRAN + PLIN** | ✅ **SÍ** | Consolidar si mismo destinatario + monto + 5 min |
| **TRAN + TARJETA** | ✅ **SÍ** | Consolidar si mismo destinatario + monto + 5 min |
| **TRAN + NFC** | ✅ **SÍ** | Consolidar si mismo destinatario + monto + 5 min |
| **PLIN + TARJETA** | ✅ **SÍ** | Consolidar si mismo destinatario + monto + 5 min |
| **PLIN + NFC** | ✅ **SÍ** | Consolidar si mismo destinatario + monto + 5 min |
| **TARJETA + NFC** | ✅ **SÍ** | Consolidar si mismo destinatario + monto + 5 min |

## Flujo de Procesamiento

### Escenario 1: NFC primero → Interbank TARJETA
1. NFC: "S/ 63.67 con Infinite ••9820" → Registrar con motivo
2. Interbank: "Realizaste un consumo de S/ 63.67 en IZICORRALITO..." → Detectar consolidación → Actualizar registro (NO solicitar nada nuevo)

### Escenario 2: Interbank TARJETA primero → NFC
1. Interbank: "Realizaste un consumo de S/ 63.67 en IZICORRALITO..." → Registrar con motivo
2. NFC: "S/ 63.67 con Infinite ••9820" → Detectar consolidación → Actualizar registro (NO solicitar nada nuevo)

### Escenario 3: Mismo tipo (ej. NFC + NFC)
1. NFC primero → Registrar con motivo
2. NFC segundo → **NUNCA duplicado** → Insertar como registro independiente

### Escenario 4: Secuencia TRAN → TARJETA → PLIN
1. TRAN: Registrar con motivo y monto
2. TARJETA: Monto vacío → Solicitar al usuario → Consolidar con TRAN
3. PLIN: Consolidar con registro TRAN+TARJETA → Marcar como consolidado

## Comandos de Uso

```bash
# Instalar entorno
cd /home/giancarlo/local-gestion-gastos
bash instalacion.sh

# Listar transacciones
python3 main.py --accion listar

# Insertar transacción manual
python3 main.py --accion insertar \
  --motivo "Pago de servicio público" \
  --tipo gasto \
  --monto 15.50 \
  --destinatario "Empresa de Servicios"

# Ver logs
cat ~/.local_gestion_gastos/app.log
```

## Licencia y Mantenimiento
- **Desarrollador**: local-gestion-gastos
- **Entorno**: Termux/Linux (Python 3.8+)
- **Última actualización**: Noviembre 2026
- **Licencia**: Uso interno/no comercial

## Cambios Recientes
- ✅ Agregado soporte NFC (walletnfcrel)
- ✅ Reglas de duplicados: Mismo tipo NUNCA duplicado
- ✅ Consolidación entre tipos diferentes
- ✅ Logging paso a paso en main.py
- ✅ Script de instalación bash
- ✅ Actualización de diagramas UML
- ✅ Actualización de documentación markdown (10+ archivos)
- ✅ PDFs generados a partir de markdown