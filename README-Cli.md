# Interfaz de Línea de Comandos (CLI) - local-gestion-gastos

Documentación detallada de todas las funcionalidades del sistema a través de la línea de comandos, con diferenciación clara entre **acción** y **modo**.

---

## 1. Conceptos Fundamentales: Acción vs. Modo

Antes de ver los comandos, es importante entender la diferencia entre estos dos conceptos:

### Acción ( `--accion` )
**Qué quieres hacer** con el sistema. Define la operación principal.

| Acción | Qué hace |
|--------|----------|
| `listar` | Muestra transacciones almacenadas en SQLite |
| `sync` | Envía transaccencias pendientes a la nube (Google Cloud Function) |
| `insert` | Agrega una nueva transacción manualmente |
| `automate_broker` | Procesa archivos JSON dejados por la aplicación **Automate** en un directorio |
| `listener` | Captura notificaciones directas usando las API de Termux |

**Ejemplo:** `python3 main.py --accion listar` → "Quiero ver mis transacciones guardadas"

### Modo ( `--modo` )
**Cómo debería operar** el sistema durante esa acción. Solo es necesario especificarlo en ciertos casos.

| Modo | Describe el comportamiento |
|------|---------------------------|
| `automate_broker` | El sistema procesa archivos JSON que Automate dejó en un directorio. Este es el modo por defecto para la acción `automate_broker`. |
| `listener_directo` | El sistema captura notificaciones directamente usando las API de Termux. Este es el modo por defecto para la acción `listener`. |

**Regla general:**
- Para la acción `automate_broker`, el modo por defecto es `automate_broker` (a menos que quieras sobreescribirlo)
- Para la acción `listener`, el modo por defecto es `listener_directo` (por eso **no es necesario** pasar `--modo listener_directo` cada vez)
- Puedes sobrescribir el modo default usando el flag `--modo` si es necesario

**Ejemplo:** `python3 main.py --accion automate_broker` → "Quiero procesar archivos de Automate usando el modo broker por defecto"

---

## 2. Comandos Principales (Flags)

El sistema ofrece los siguientes comandos principales a través de `main.py`:

### `python3 main.py --accion listar`

**Descripción:** Muestra las últimas transacciones registradas en la base de datos local.

**Flag:** `--accion listar` (es el default, pero puede especificarse explícitamente)

**Ejemplos:**
```bash
# Modo básico (accion es el default)
python3 main.py

# Con flag explícito
python3 main.py --accion listar

# Resultado muestra:
# 📊 Últimas 10 transacciones:
#   - 2026-11-22 | gasto | S/ 25.00 | Supermercado
```

---

### `python3 main.py --accion sync`

**Descripción:** Sincroniza las transacciones pendientes con la nube (Google Cloud Function → Google Sheets → Looker Studio).

**Flag:** `--accion sync`

**Ejemplos:**
```bash
# Sincronizar transacciones pendientes
python3 main.py --accion sync

# Resultado:
# 🔄 Sincronizando transacciones pendientes...
# 📋 3 transacciones pendientes de sincronizar
# ✅ 3 transacciones marcadas como sincronizadas (demo)
```

---

### `python3 main.py --accion insert`

**Descripción:** Inserta una transacción manual desde la CLI. Requiere todos los datos del movimiento.

**Flags obligatorios:**

| Flag | Descripción | Ejemplo |
|------|-------------|---------|
| `--motivo` | Razón o descripción del movimiento | `--motivo "Compra en mercado"` |
| `--tipo` | Tipo de movimiento (`ingreso` o `gasto`) | `--tipo gasto` |
| `--monto` | Monto en Soles (debe ser > 0) | `--monto 25.50` |
| `--destinatario` | Persona o comercio beneficiado/afectado | `--destinatario "Supermercado"` |

**Ejemplos:**
```bash
# Insertar un gasto manual
python3 main.py --accion insert \
  --motivo "Pago de servicio público" \
  --tipo gasto \
  --monto 15.50 \
  --destinatario "Empresa de Servicios"

# Resultado:
# ✅ Transacción registrada manualmente!
#   event_id: 4d6a7b8c-9e0f-1234-5678-9abcdef01234
#   Motivo: Pago de servicio público
#   Monto: S/ 15.50
#   Tipo: gasto
#   Destinatario: Empresa de Servicios
#   Sincronizado: NO (0) - Ejecute 'python3 main.py --sync' para enviar a la nube

# Insertar un ingreso manual
python3 main.py --accion insert \
  --motivo "Depósito de nómina" \
  --tipo ingreso \
  --monto 1200.00 \
  --destinatario "Employer Corp"
```

**Validaciones:**
- Si falta `--motivo`: ❌ Error: Se requiere --motivo
- Si `--tipo` no es `ingreso` o `gasto`: ❌ Error: Se requiere --tipo válido
- Si `--monto` ≤ 0: ❌ Error: El monto debe ser > 0
- Si falta `--destinatario`: ❌ Error: Se requiere --destinatario

---

### `python3 main.py --accion automate_broker`

**Descripción:** Procesa archivos JSON dejados por la aplicación **Automate** en un directorio, usando el modo **Automate Broker**. Este es el flujo principal para procesar notificaciones bancarias automáticamente.

**Diferencia clave con la versión anterior:**
- Antes se usaba `--accion fifo`, ahora se usa `--accion automate_broker` (más descriptivo)

**Flags opcionales:**

| Flag | Descripción | Default | Sobrescribe |
|------|-------------|---------|-------------|
| `--directorio` | Directorio donde Automate deja los archivos JSON | De `config.yaml` | Sí, si se especifica |
| `--modo` | Modo de operación | `automate_broker` (por defecto) | No usualmente necesario |

**Comportamiento detallado:**

1. **Lector de directorio:** Lee todos los archivos del directorio especificado (o de `config.yaml`)
2. **Ordenamiento FIFO:** Ordena por fecha de creación (first-in, first-out)
3. **Extracción de `package`:** Para cada archivo, lee la propiedad `package` del JSON
4. **Consulta de adaptador:** Busca en `config.yaml` `mapeo_adaptadores` para decidir el adaptador:
   - `pe.com.interbank.mobilebanking` → `IBKAdapter`
   - `com.bcp.innovacxion.yapeapp` → `YapeAdapter`
5. **Normalización:** El adaptador correspondiente extrae monto, tipo, destinatario usando sus regex
6. **Solicitud de motivo:** Si es necesario, invoca `termux-dialog` para obtener el motivo
7. **Obtención de GPS:** Usa `termux-location` con respaldo offline
8. **Guardado en SQLite:** Guarda la transacción en `local_gastos.db`

**Ejemplos:**

```bash
# Modo default - usa directorio de config.yaml
python3 main.py --accion automate_broker

# Output esperado en consola:
# 🔄 Modo Automate Broker: procesando archivos de /sdcard/Automate/notify
# 📁 Directorio: /sdcard/Automate/notify
# 📦 Paquetes: 5
# Se encontraron 3 archivos nuevos
# Adaptador: IBKAdapter o YapeAdapter
# Monto: S/ 20.00, Tipo: gasto, Destinatario: Juan Pérez
# ⏳ Solicitando motivo vía termux-dialog...
# ✅ Transacción guardada en SQLite: event_id_123

# Con directorio personalizado (sobreescribe config.yaml)
python3 main.py --accion automate_broker --directorio /sdcard/Automate/mi_notificaciones

# Output:
# 🔄 Modo Automate Broker: procesando archivos de /sdcard/Automate/mi_notificaciones
# 📁 Directorio: /sdcard/Automate/mi_notificaciones
```

### `python3 main.py --accion listener`

**Descripción:** Captura notificaciones directas usando **Termux API** sin necesidad de que Automate entregue archivos. Este modo usa `termux-notification-list` para leer notificaciones entrantes.

**Diferencia clave:**
- **`--accion listener`** = Quiero capturar notificaciones directas
- **¿Para `--modo`?** No es necesario especificarlo - el sistema defaulta automáticamente a `listener_directo`

**Flags opcionales:**

| Flag | Descripción | Default |
|------|-------------|---------|
| `--directorio` | Directorio para almacenar datos temporales | `/tmp/termux_notifications` |

**Comportamiento detallado:**

1. **Lectura de notifications:** Usa `termux-notification-list -p <paquete>` para leer notificaciones
2. **Filtrado por paquetes:** Solo procesa notificaciones de bancos monitoreados (`PAQUETES_BANCOS`)
3. **Para cada notificación:**
   - Extrae los datos crudos del mensaje
   - Invoca el adaptador correspondiente (basado en el paquete)
   - Normaliza los datos (monto, tipo, destinatario usando regex)
   - Solicita motivo vía `termux-dialog` si está disponible
   - Obtiene GPS vía `termux-location` (con respaldo: última conocida o none)
4. **Guardado en SQLite:** Almacena la transacción

**Ejemplos:**

```bash
# Capturar notificaciones directas (modo default)
python3 main.py --accion listener

# Output:
# 🔄 Modo Listener Directo: capturando notificaciones
# 🚀 Iniciando FIFO-Cola en modo: listener_directo
# 📁 Directorio: /tmp/termux_notifications
# 📦 Paquetes monitorizados: 5
# Verificando notificaciones entrantes...
# Encontradas notificaciones de: com.bcp.innovacxion.yapeapp
# Procesando notificación Yape...
# Monto: S/ 15.00, Tipo: ingreso, Destinatario: María González
# ⏳ Solicitando motivo vía termux-dialog...
# ✅ Transacción guardada en SQLite

# Con directorio personalizado
python3 main.py --accion listener --directorio /data/data/com.termux/files/home/notify

# Output:
# 🔄 Modo Listener Directo: capturando notificaciones
# 📁 Directorio: /data/data/com.termux/files/home/notify
```

---

## 3. Diferencia entre Acción y Modo (Resumida)

| Concepto | Valor | Descripción |
|----------|-------|-------------|
| `--accion` | `listar`, `sync`, `insert`, `automate_broker`, `listener` | **Qué hacer** - operación principal |
| `--modo` | `automate_broker`, `listener_directo` | **Cómo hacerlo** - estilo de operación |

### Cuándo usar cada combinación:

| Escenario | `--accion` | `--modo` | `--directorio` |
|-----------|------------|----------|----------------|
| Ver transacciones | `listar` | (ninguno) | (ninguno) |
| Sincronizar con nube | `sync` | (ninguno) | (ninguno) |
| Insertar movimiento manual | `insert` | (ninguno, requiere `--motivo --tipo --monto --destinatario`) | (ninguno) |
| Procesar JSON de Automate | `automate_broker` | `automate_broker` (default) | Opcional (`--directorio`) |
| Capturar notificaciones Termux | `listener` | `listener_directo` (default) | Opcional (`--directorio`) |

**Ejemplos de combinaciones:**

```bash
# Usado común: procesar Automate con defaults
python3 main.py --accion automate_broker

# Personalizado: procesar JSON de otro directorio
python3 main.py --accion automate_broker --directorio /home/usuario/Automate/notifications

# Solo captura Termux (sin Automate)
python3 main.py --accion listener

# Insertar movimiento manual
python3 main.py --accion insert \
  --motivo "Compra" \
  --tipo gasto \
  --monto 10 \
  --destinatario "Tienda"

# Flujo completo Automate → Procesar → Sincronizar
python3 main.py --accion automate_broker
python3 main.py --accion listar
python3 main.py --accion sync
```

---

## 4. Detalle del Directorio de Automate (config.yaml)

A diferencia de sistemas anteriores, **el directorio donde Automate deja los archivos JSON ahora viene configurado en `config.yaml`**, no como parámetro obligatorio en cada ejecución.

### Configuración en `config.yaml`:

```yaml
# --- Directorio de Archivos Automate ---
directorio_archivos_automate: "/sdcard/Automate/notify"
  # Puedo personalizar según entorno:
  # - En Termux/Linux: /home/usuario/Automate/notify
  # - En Android real: /sdcard/Automate/notify
```

### Flujo de trabajo:

1. **Configuración inicial:** El usuario establece `directorio_archivos_automate` en `config.yaml`
2. **Ejecución normal:** `python3 main.py --accion automate_broker` lee automáticamente de `config.yaml`
3. **Sobrescritura opcional:** `python3 main.py --accion automate_broker --directorio /ruta/personalizada` si se necesita cambiar temporalmente

### Sin flag `--directorio`:
El sistema usará el valor de `config.yaml`, lo que hace el flujo más limpio y centralizado.

---

## 5. Ejemplos Prácticos

### Ejemplo 1: Procesar JSON de Automate (recomendado)

```bash
# Modo default - procesa usando directorio de config.yaml
python3 main.py --accion automate_broker

# Con directorio personalizado
python3 main.py --accion automate_broker --directorio /sdcard/Automate/mi_notificaciones
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

### Ejemplo 5: Flujo completo (Automate → Procesar → Sincronizar)

```bash
# Paso 1: Procesar archivos dejados por Automate
python3 main.py --accion automate_broker

# Salida:
# 🔄 Modo Automate Broker: procesando archivos de /sdcard/Automate/notify
# 📁 Directorio: /sdcard/Automate/notify
# 📦 Paquetes: 5
# Se encontraron 3 archivos nuevos
# Adaptador IBKAdapter para: pe.com.interbank.mobilebanking
# Adaptador YapeAdapter para: com.bcp.innovacxion.yapeapp
# 3 transacciones guardadas en SQLite
# Procesamiento broker Automate finalizado

# Paso 2: Revisar qué se guardó
python3 main.py --accion listar

# Salida:
# 📊 Últimas 10 transacciones:
#   - 2026-11-22 | gasto | S/ 20.00 | Juan Pérez
#   - 2026-11-22 | ingreso | S/ 15.50 | María Gómez
#   - 2026-11-22 | gasto | S/ 50.00 | Supermercado

# Paso 3: Sincronizar con la nube
python3 main.py --accion sync

# Salida:
# 🔄 Sincronizando transacciones pendientes...
# 📋 3 transacciones pendientes de sincronizar
# ✅ 3 transacciones marcadas como sincronizadas (demo)
# ✅ Sincronización completada
```

### Ejemplo 4: Combinaciones de flags

```bash
# Usado común: procesar Automate con defaults
python3 main.py --accion automate_broker

# Personalizado: procesar JSON de otro directorio
python3 main.py --accion automate_broker --directorio /sdcard/Automate/notify

# Usado común: capturar notificaciones Termux
python3 main.py --accion listener

# Con modo explícito (aunque ya es default)
python3 main.py --accion listener --modo listener_directo

# Insertar movimiento manual
python3 main.py --accion insert \
  --motivo "Compra supermercado" \
  --tipo gasto \
  --monto 25.50 \
  --destinatario "Supermercado"
```

---

## 6. Resumen de Flags Disponibles

| Flag | Acción | Descripción |
|------|--------|-------------|
| `--accion listar` | listar | Ver transacciones en SQLite |
| `--accion sync` | sync | Sincronizar con nube |
| `--accion insert` | insert | Insertar manual con `--motivo --tipo --monto --destinatario` |
| `--accion automate_broker` | automate_broker | Procesar archivos JSON de Automate de directorio |
| `--accion listener` | listener | Capturar notificaciones directas via Termux API |
| `--directorio RUTA` | automate_broker/listener | Directorio personalizado (sobreescribe `config.yaml`) |
| `--modo MODE` | automate_broker/listener | `automate_broker` (default para automate_broker) o `listener_directo` (default para listener) |

**Ejemplo completo con todos los flags:**
```bash
python3 main.py --accion automate_broker --directorio /sdcard/Automate/notify --modo automate_broker
```

**O simplemente, usando defaults:**
```bash
python3 main.py --accion automate_broker
# (usa config.yaml automáticamente)

# O para listener:
python3 main.py --accion listener
# (defaulta automáticamente a listener_directo)
```