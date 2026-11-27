# local-gestion-gastos

Sistema de gestión de gastos e ingresos para Android/Termux que procesa notificaciones bancarias de 4 formatos: TRAN, PLIN, TARJETA, NFC.

## Características Principales
- Soporte de 4 formatos de notificación: TRAN, PLIN, TARJETA, NFC
- Regla de duplicados: Mismo tipo NUNCA es duplicado
- Consolidación entre tipos diferentes (mismo destinatario + monto + ventana 5 min)
- Logging paso a paso en `~/.local_gestion_gastos/app.log`
- CLI con comandos `listar` y `insertar`
- Script de instalación automática

## Formatos Soportados
- **TRAN**: Transferencias bancarias
- **PLIN**: Pagos P2P
- **TARJETA**: Consumos con tarjeta
- **NFC**: Google Pay / Wallet

## Comandos Disponibles

Todos los comandos funcionan en **Termux (Android)** y **Linux**.

```bash
# Modo definido en config.yaml (modo_operacion)
python3 main.py

# Modos de operación (daemon)
python3 main.py --broker            # Automate File Broker
python3 main.py --broker --once     # Procesar un ciclo y salir
python3 main.py --listener          # Listener directo (SOLO Termux)

# Ver transacciones (tabla / JSON)
python3 main.py --accion listar
python3 main.py --accion listar --json

# Insertar transacción manual
python3 main.py --accion insertar \
  --motivo "Motivo del movimiento" \
  --monto 15.50 \
  --tipo gasto \
  --destinatario "Beneficiario"

# Flujo interactivo completo (incluye GPS)
python3 main.py --accion registro

# Consultas SQL personalizadas (tabla / JSON)
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5"
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5" --json

# Marcar transacciones pendientes como sincronizadas
python3 main.py --accion sync

# Ver ayuda
python3 main.py --help
```

> La base de datos se toma de `config.yaml` (`bd.ruta_sqlite`) y se crea
> automáticamente. Los proveedores se eligen según el entorno (Termux/Linux).

## Flujo del modo broker (archivo único)

Automate captura cada notificación y la escribe en **un único archivo JSON**,
**reescribiéndolo** en cada notificación. El broker hace polling, detecta el
cambio y lo procesa en orden (FIFO de un archivo).

- **Termux:** `config.yaml` → `automate_broker.archivo_notificacion`
  (`.../storage/shared/Documents/noti.json`).
- **Linux:** `./noti_inbox/noti.json` (fijo, para pruebas).

```yaml
automate_broker:
  activado: true
  archivo_notificacion: "/data/data/com.termux/files/home/storage/shared/Documents/noti.json"
  monitoreo_polling_segundos: 5
```

Pipeline: leer cambio → parsear JSON → **registrar crudo tal cual en
`notificaciones_crudas`** → enrutar al adaptador del banco → normalizar →
**preguntar datos faltantes** (monto/tipo/destinatario/motivo: `termux-dialog` en
Termux, `input()` en Linux) → duplicados/consolidación → **validar todas las
reglas** → GPS → insertar en `transacciones` (`sincronizado=0`) → actualizar crudo
a `procesada` → **eliminar `noti.json`** al terminar.

- Solo se guarda en `transacciones` si cumple **todas** las reglas (monto > 0,
  tipo gasto/ingreso, destinatario y motivo válidos). Si faltan datos, el crudo
  queda como `incompleta` y no se crea transacción.
- Idempotencia: cambio detectado por `(mtime_ns, tamaño, SHA-1)` persistido en
  `.broker_state.json`; JSON incompleto se reintenta. En error grave (crudo/BD) el
  archivo se conserva para reintento.
- Logs en consola y en `./logs/app.log` (rotación según `logging.rotacion`).

📖 Detalle completo (diagrama de secuencia, errores, diferencias Termux/Linux):
**`docs/FLUJO-BROKER.md`**.

## Base de Datos

- **Motor:** SQLite.
- **Ubicación:** definida en `config.yaml` → `bd.ruta_sqlite` (por defecto `./local_gastos.db`,
  es decir, en la raíz del proyecto).
- **Creación:** automática al primer uso (`inicializar()` crea las tablas si no existen
  y aplica migraciones ligeras, p. ej. columna `fecha_iso`).

### ¿Cómo se guardan los datos?

Hay un **único punto de escritura**: `infraestructura/database_provider.py::insertar_transaccion()`.
Todas las vías pasan por ahí:

| Vía | Comando / flujo | Qué hace |
|-----|-----------------|----------|
| Registro interactivo | `--accion registro` / `--registro` | Pide motivo, monto, destinatario, GPS y confirma; inserta. |
| Inserción con flags | `--accion insertar --motivo ... --monto ...` | Inserta directo (si faltan datos, los pide). |
| Automático (broker) | `--broker` | Lee el JSON, **registra el crudo**, enruta al adaptador, pide faltantes, valida reglas, GPS, inserta y **borra el archivo**. |
| Automático (listener) | `--listener` (solo Termux) | Captura notificación nativa, normaliza e inserta. |

> **`notificaciones_crudas`** recibe **todo** lo que entra (log tal cual, `cuerpo` =
> JSON completo) mediante `insertar_notificacion_cruda()`, aunque luego no se cree
> una transacción (queda `incompleta`, `duplicado`, `ignorada_*`, etc.).

Detalles de la escritura:
- `id_transaccion` = `event_id` (UUID o `notification_id`) **UNIQUE** → evita duplicados.
- `sincronizado = 0` por defecto (pendiente de subir a la nube).
- `fuente_gps` queda en `live` / `ip-geolocation` / `sqlite-history` / `none`.
- Si el GPS falla, el registro **igual se guarda** (lat/lng NULL, `fuente_gps = none`).

### ¿Cómo se listan los datos?

| Vía | Comportamiento |
|-----|----------------|
| `--accion listar [--json]` | Últimas N transacciones ordenadas por `fecha_hora_epoch DESC` (más recientes primero). **Recomendado.** |
| `--accion sql --sql "..."` | SQL libre. ⚠️ `LIMIT` **sin `ORDER BY`** devuelve las filas **más antiguas** (por `rowid`). Para ver las recientes use `ORDER BY id DESC` o `ORDER BY fecha_hora_epoch DESC`. |

Ejemplo: lo que se guardó en `--accion registro` aparece al final; para verlo:

```bash
python3 main.py --accion listar --limit 5
python3 main.py --accion sql --sql "SELECT * FROM transacciones ORDER BY id DESC LIMIT 5" --json
```

### Tablas

#### 1. `transacciones` (tabla principal)
Una fila por movimiento financiero.

| Grupo | Columnas | Descripción |
|-------|----------|-------------|
| Identificación | `id`, `id_transaccion` | `id` autonumérico; `id_transaccion` = UUID/event_id **UNIQUE**. |
| Tiempo | `fecha_hora_epoch`, `fecha_iso`, `fecha`, `hora`, `trimestre` | Momento del movimiento en varios formatos. |
| Origen | `app`, `paquete`, `dispositivo` | App/paquete Android y dispositivo que originó el registro. |
| Clasificación | `tipo`, `medio`, `monto_total`, `moneda`, `destinatario`, `motivo`, `categoria` | `tipo` = `gasto`/`ingreso`; monto en `moneda` (PEN). |
| Préstamos | `es_prestamo`, `monto_pagado`, `saldo_pendiente`, `estado_prestamo` | Seguimiento de deudas (`activo`/`parcial`/`saldado`/`n/a`). |
| Analítica | `looker` | Indicador para reportes (Looker Studio). |
| Ubicación | `latitud`, `longitud`, `fuente_gps` | Coordenadas y su origen (`live`, `ip-geolocation`, `sqlite-history`, `none`). |
| Auditoría | `mensaje_raw` | Texto original de la notificación. |
| Estado/sync | `status`, `sincronizado`, `intentos_sync`, `ultimo_error_sync` | `status` (`consolidado`), `sincronizado` 0/1, reintentos y último error. |

#### 2. `notificaciones_crudas` (log de TODO lo que ingresa)
Es la **auditoría**: se guarda **cada notificación tal cual llega** (aunque después
no genere transacción), para poder depurar o reprocesar.

| Columna | Descripción |
|---------|-------------|
| `id` | Autonumérico. |
| `recibido_en` | Epoch en que se recibió. |
| `paquete`, `app`, `dispositivo` | Origen Android (paquete, app/título, device). |
| `titulo`, `cuerpo` | `titulo` = title; `cuerpo` = **JSON completo tal cual**. |
| `id_transaccion_vinculada` | FK lógica a `transacciones.id_transaccion` (si se guardó). |
| `resultado_proceso` | `recibida`, `procesada`, `duplicado`, `incompleta`, `ignorada_paquete_no_mapeado`, `error_bd`, … |

#### 3. `abonos_prestamo` (préstamos: yo presté / me prestaron)
Registra **abonos** que referencian transacciones de préstamo. La transacción de
préstamo (dinero prestado o recibido) vive en `transacciones`; aquí se registran
los pagos parciales que la saldan.

| Columna | Descripción |
|---------|-------------|
| `id` | Autonumérico. |
| `id_transaccion_prestamo` | FK lógica a la transacción de préstamo (la deuda original). |
| `id_transaccion_ingreso` | FK lógica al movimiento que paga/abona la deuda. |
| `fecha_abono` | Fecha del abono. |
| `monto_abono` | Monto pagado. |
| `saldo_restante` | Saldo después del abono. |
| `nota` | Observaciones. |

> Se registra con `infraestructura/database_provider.py::insertar_abono(...)`.

### Consultas de verificación útiles

```bash
# Último registro guardado
python3 main.py --accion sql --sql "SELECT * FROM transacciones ORDER BY id DESC LIMIT 5"

# Buscar por event_id
python3 main.py --accion sql --sql "SELECT * FROM transacciones WHERE id_transaccion='4d478909-2011-45df-8f08-ac8f443db439'"

# Contar registros
python3 main.py --accion sql --sql "SELECT COUNT(*) AS total FROM transacciones"

# Pendientes de sincronizar
python3 main.py --accion sql --sql "SELECT id_transaccion, monto_total FROM transacciones WHERE sincronizado=0"

# Ver todo lo que ingresó (log crudo) y su resultado
python3 main.py --accion sql --sql "SELECT id, paquete, titulo, resultado_proceso, recibido_en FROM notificaciones_crudas ORDER BY id DESC LIMIT 10"

# Ver abonos de préstamos
python3 main.py --accion sql --sql "SELECT * FROM abonos_prestamo ORDER BY id DESC LIMIT 10"
```

## Documentación
- `docs/`: Diagramas UML y documentación PDF