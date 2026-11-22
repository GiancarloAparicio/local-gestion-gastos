# Interfaz de Línea de Comandos (CLI) - local-gestion-gastos

Documentación completa de todas las funcionalidades del sistema a través de la línea de comandos, incluyendo cómo gatillar el sistema con archivos JSON dejados por Automate y cómo operar completamente con Termux API.

---

## 1. Comandios Disponibles (usando flags)

El sistema ofrece los siguientes comandos principales a través de `main.py` usando **flags** (bandera/switch):

### `python3 main.py --accion listar`
- **Descripción:** Lista las últimas transacciones registradas en la base de datos local.
- **Flag:** `--accion listar` (o simplemente `--accion` con valor `listar`)
- **Uso típico:** Revisar el historial de movimientos ya procesados.
- **Ejemplo:**
  ```bash
  python3 main.py --accion listar
  ```
- **Salida:** Muestra las últimas 10 transacciones con fecha, tipo, monto y destinatario.

### `python3 main.py --accion sync`
- **Descripción:** Sincroniza las transacciones pendientes con la nube (Google Cloud Function).
- **Flag:** `--accion sync`
- **Uso típico:** Después de procesar notificaciones, enviar los datos a Google Sheets/Looker Studio.
- **Ejemplo:**
  ```bash
  python3 main.py --accion sync
  ```
- **Comportamiento:** Lista hasta 100 transacciones con `sincronizado=0` y marca las primeras 3 como sincronizadas (modo demo).

### `python3 main.py --accion insert`
- **Descripción:** Inserta una transacción manual desde la CLI.
- **Flags requeridos:**
  - `--motivo` - Razón del movimiento (obligatorio)
  - `--tipo` - Tipo de movimiento (`ingreso` o `gasto`) (obligatorio)
  - `--monto` - Monto del movimiento (obligatorio, debe ser > 0)
  - `--destinatario` - Persona o comercio (obligatorio)
- **Ejemplo:**
  ```bash
  python3 main.py --accion insert --motivo "Compra en mercado" --tipo gasto --monto 25.00 --destinatario "Supermercado"
  ```
- **Salida:** Confirma el registro con el event_id generado y muestra el estado de sincronización.

### `python3 main.py --accion fifo`
- **Descripción:** Procesa archivos JSON dejados por Automate usando el modo **Automate Broker**.
- **Flags opcionales:**
  - `--directorio` - Directorio donde Automate deja los archivos (default: `/sdcard/Automate/notify` o variable `DIRECTORIO_NOTIFICACIONES`)
  - `--modo` - Modo operación: `automate_broker` (default) o `listener_directo`
- **Uso típico:** Cuando Automate ha interceptado notificaciones y entregado archivos JSON al sistema.
- **Ejemplo:**
  ```bash
  # Modo default (automate_broker)
  python3 main.py --accion fifo

  # Con directorio personalizado
  python3 main.py --accion fifo --directorio /sdcard/Automate/mi_notificaciones

  # Con modo listener especificado
  python3 main.py --accion fifo --modo listener_directo
  ```
- **Comportamiento:** Lee los archivos del directorio, ordena por fecha (FIFO), para cada archivo extrae la propiedad `package`, consulta `config.yaml` para decidir el adaptador (IBKAdapter, YapeAdapter, etc.), normaliza los datos, solicita motivo si es necesario (vía termux-dialog), obtiene GPS (vía termux-location) y guarda en SQLite.

### `python3 main.py --accion listener`
- **Descripción:** Captura notificaciones directas usando **Termux API** sin necesidad de que Automate entregue archivos.
- **Flags opcionales:**
  - `--directorio` - Directorio para almacenar datos temporales
- **Uso típico:** Cuando se quiere capturar notificaciones directamente desde Termux en Android usando `termux-notification-list`.
- **Ejemplo:**
  ```bash
  # Capturar notificaciones directas
  python3 main.py --accion listener

  # Con directorio personalizado
  python3 main.py --accion listener --directorio /tmp/termux_notificaciones
  ```
- **Comportamiento:** Usa `termux-notification-list` para leer notificaciones entrantes, filtra por paquetes de bancos monitoreados, para cada notificación invoca el adaptador correspondiente, solicita motivo vía `termux-dialog` si está disponible, obtiene GPS vía `termux-location` y guarda en SQLite local.

---

## 2. Gatillado con Archivo JSON de Automate

Cuando la aplicación **Automate** (en Android) intercepta una notificación bancaria, puede entregar un archivo JSON al entorno Termux. El sistema está preparado para procesar estos archivos directamente usando flags.

### Estructura del JSON que deja Automate

El archivo JSON típicamente contiene propiedades como:

```json
{
  "package": "pe.com.interbank.mobilebanking",
  "content": "Plineaste S/ 20.00 a Nombre User",
  "title": "Interbank",
  "when": 1732857600.0
}
```

### Cómo procesar el archivo JSON usando flags

1. **Comando principal:**
   ```bash
   python3 main.py --accion fifo
   ```

2. **Con directorio personalizado (usando flag `--directorio`):**
   ```bash
   python3 main.py --accion fifo --directorio /sdcard/Automate/mi_notificaciones
   ```

3. **El sistema hace lo siguiente automáticamente:**
   - Lee los archivos del directorio especificado
   - Ordena por fecha (FIFO - First In, First Out)
   - Para cada archivo, extrae la propiedad `package`
   - Consulta `config.yaml` `mapeo_adaptadores` para decidir el adaptador:
     - `pe.com.interbank.mobilebanking` → `IBKAdapter`
     - `com.bcp.innovacxion.yapeapp` → `YapeAdapter`
   - Normaliza los datos (extrae monto, tipo, destinatario usando las regex de cada adaptador)
   - Solicita motivo al usuario vía `termux-dialog` si es necesario
   - Obtiene ubicación GPS vía `termux-location` (con respaldo offline)
   - Guarda todo en `local_gastos.db` (SQLite)
   - Marca como listo para sincronización

### Flujo completo con flags:

```
Automate (Android)
    ↓ deja archivo JSON en /sdcard/Automate/notify/
    ↓
python3 main.py --accion fifo [--directorio /ruta/personalizada]
    ↓
FIFOCola lee el JSON
    ↓
Extrae propiedad "package"
    ↓
config.yaml mapeo_adaptadores decide IBKAdapter o YapeAdapter
    ↓
Adaptador.normalizar_notificacion(datos) -> diccionario normalizado
    ↓
¿Solicita motivo?
    ↓
  Sí → termux_dialog pregnancy "¿Cuál fue el motivo?"
    ↓
No → continúa
    ↓
¿Obtener GPS?
    ↓
  Sí → termux_location obtener_coordenadas
    ↓
No → usar último conocido o none
    ↓
Guardar en SQLite local_gastos.db
    ↓
Listo para: python3 main.py --accion sync
```

---

## 3. Operación Completa con Termux API

El sistema puede operar enteramente desde Termux en Android, usando las APIs de Termux para diálogos y ubicación. Todo mediante **flags**.

### 3.1 Modo listener_directo (captura directa de notificaciones)

Este modo captura notificaciones directamente usando Termux API, sin necesidad de que Automate entregue archivos. Usa flag `--accion listener`.

```bash
python3 main.py --accion listener
```

**Qué hace:**
- Usa `termux-notification-list` para leer notificaciones entrantes
- Filtra por paquetes de bancos monitoreados (`PAQUETES_BANCOS`)
- Para cada notificación, invoca el adaptador correspondiente
- Solicita motivo vía `termux-dialog` si está disponible
- Obtiene GPS vía `termux-location` (con respaldo offline)
- Guarda en SQLite local

**Ejemplo práctico:**
```bash
# Capturar y procesar notificaciones directas
python3 main.py --accion listener
```

### 3.2 Modo automate_broker (procesa archivos de Automate)

Este es el modo por defecto, ideal cuando Automate entrega archivos JSON. Usa flag `--accion fifo`.

```bash
python3 main.py --accion fifo
```

**O con opciones adicionales:**
```bash
# Con directorio personalizado
python3 main.py --accion fifo --directorio /sdcard/Automate/mi_notificaciones

# Modo listener explícito (aunque fifo ya usa automate_broker por default)
python3 main.py --accion fifo --modo listener_directo
```

### 3.3 Solicitar motivo mediante termux-dialog (usando flags)

Cuando el sistema necesita el motivo de un movimiento (para consolidar o registros nuevos), invoca el diálogo automáticamente. También se puede invocar directamente:

```bash
# El sistema lo hace automáticamente durante el flujo fifo/listener
# Pero también se puede invocar directamente desde la línea de comandos:
python3 -c "
from modulios.termux_api import termux_api
resultado = termux_api.mostrar_dialogo(
    widget='text',
    titulo='Motivo del movimiento',
    mensaje='¿Cuál fue el motivo de este movimiento? '
)
if resultado and 'text' in resultado:
    print('Motivo ingresado:', resultado['text'])
"
```

Dentro del flujo con flags, el sistema preguntará automáticamente si es necesario.

### 3.4 Obtener ubicación GPS (usando flags)

Dentro del flujo `--accion fifo` o `--accion listener`, el sistema obtiene GPS automáticamente:

```bash
# El sistema usa termux-location internamente
python3 main.py --accion fifo

# O ver la ubicación como paso independiente:
python3 -c "
from modulios.termux_api import termux_api
ubicacion = termux_api.obtener_ubicacion()
print('Latitud:', ubicacion.get('latitud'))
print('Longitud:', ubicacion.get('longitud'))
print('Fuente GPS:', ubicacion.get('fuente_gps'))
"
```

### 3.5 Flujo completo Termux (offline-first) usando flags

```bash
# Paso 1: Procesar archivos dejados por Automate (usando flag fifo)
python3 main.py --accion fifo

# El sistema procesará los archivos JSON:
# - Leerá cada archivo del directorio /sdcard/Automate/notify
# - Extraerá la propiedad 'package' para decidir el adaptador (IBKAdapter/YapeAdapter)
# - Normalizará los datos (monto, tipo, destinatario)
# - Solicitará motivo vía termux-dialog si es necesario
# - Obtendrá GPS vía termux-location (con respaldo offline)
# - Guardará todo en local_gastos.db (SQLite)

# Paso 2: Revisar los registros guardados (usando flag listar)
python3 main.py --accion listar

# Paso 3: Sincronizar con la nube (usando flag sync)
python3 main.py --accion sync
```

---

## 4. Configuración del Flujo

### `config.yaml` - Personalización

El archivo `config.yaml` concentra toda la configuración. **Las flags del CLI usan estos valores por defecto, pero pueden sobreescribirse:**

```yaml
# --- Mapeo de Paquetes a Adaptadores ---
# Configuración del paquete (property "package" del JSON de Automate)
# para decidir qué adaptador usar. Las claves son los patrones de paquete
# y los valores son los nombres de los adaptadores (sin el sufijo "Adapter").
mapeo_adaptadores:
  pe.com.interbank.mobilebanking: "ibk"
  com.bcp.innovacxion.yapeapp: "yape"
  # Más mapeos pueden añadirse aquí

# --- Modo de Operación ---
modo_operacion: "automate_broker"  # "automate_broker" o "listener_directo"

# --- Ventana de Consolidación ---
ventana_consolidacion:
  minutos: 5  # Ventana de tiempo (en minutos) para consolidar múltiples alertas

# --- Directorio donde Automate deja los archivos ---
# Se lee desde variable de entorno DIRECTORIO_NOTIFICACIONES
# o usa el default: /sdcard/Automate/notify
```

### Variables de Entorno (usadas por flags)

- `DIRECTORIO_NOTIFICACIONES`: Ruta donde Automate deja los archivos JSON (default: `/sdcard/Automate/notify`)
  - Se sobreescribe con flag `--directorio`
- `GOOGLE_CLOUD_FUNC_URL`: URL de la función Cloud para sincronización
- `GOOGLE_SHEETS_ID`: ID de la hoja de cálculo Google Sheets
- `LOOKER_STUDIO_URL`: URL de Looker Studio

---

## 5. Ejemplos Prácticos (usando flags)

### Ejemplo 1: Procesar archivos dejados por Automate

```bash
# Modo default - procesar en /sdcard/Automate/notify
python3 main.py --accion fifo

# Con directorio personalizado
python3 main.py --accion fifo --directorio /sdcard/Automate/mi_notificaciones

# Especificar modo listener (aunque fifo usa automate_broker por default)
python3 main.py --accion fifo --modo listener_directo
```

### Ejemplo 2: Capturar notificaciones directas (modo listener)

```bash
python3 main.py --accion listener

# Con directorio personalizado
python3 main.py --accion listener --directorio /tmp/termux_notificaciones
```

### Ejemplo 3: Insertar movimiento manual

```bash
python3 main.py --accion insert \
  --motivo "Pago de servicio" \
  --tipo gasto \
  --monto 15.50 \
  --destinatario "Empresa de Servicios"
```

### Ejemplo 4: Listar transacciones pendientes de sync

```bash
python3 main.py --accion sync
```

### Ejemplo 5: Combinar flags --modo y --directorio

```bash
# Usar listener_directo con directorio personalizado
python3 main.py --accion listener --directorio /data/data/com.termux/files/home/notify

# Usar fifo con modo explícito
python3 main.py --accion fifo --modo automate_broker
```

---

## 6. Estructura de Datos Resultante

Después de procesar notificaciones (ya sea usando flags `--accion fifo` o `--accion listener`), los datos se guardan en SQLite (`local_gastos.db`) en la tabla `transacciones` con campos como:

- `id_transaccion` - UUID único
- `fecha` / `hora` - Fecha y hora del movimiento
- `tipo` - `ingreso` o `gasto`
- `monto_total` - Monto en Soles (PEN)
- `destinatario` - Persona o comercio
- `motivo` - Razón del movimiento (solicitado vía termux-dialog cuando es necesario)
- `latitud` / `longitud` - Coordenadas GPS (con respaldo offline: `live`, `last_known` o `none`)
- `fuente_gps` - Origen de la ubicación (`live`, `last_known` o `none`)
- `sincronizado` - `0` (pendiente) o `1` (enviado a la nube)
- `origen_paquete` - El `package` original del JSON de Automate (ej. `pe.com.interbank.mobilebanking`)
- `canal` - `interbank`, `yape`, `nfc`, `manual`, etc.
- `fecha_hora_epoch` - Marca de tiempo epoch

---

## 7. Resumen de Flags Disponibles

| Flag | Acción | Descripción |
|------|--------|-------------|
| `--accion listar` | listar | Ver transacciones en SQLite |
| `--accion sync` | sync | Sincronizar con nube |
| `--accion insert` | insert | Insertar manual con `--motivo --tipo --monto --destinatario` |
| `--accion fifo` | fifo | Procesar archivos Automate de directorio |
| `--directorio RUTA` | fifo/listener | Directorio personalizado (sobreescribe default) |
| `--modo MODE` | fifo/listener | `automate_broker` (default) u `listener_directo` |

**Ejemplo completo con todos los flags:**
```bash
python3 main.py --accion fifo --directorio /sdcard/Automate/notify --modo automate_broker
```