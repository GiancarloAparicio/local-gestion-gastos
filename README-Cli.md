# local-gestion-gastos - CLI

Todos los comandos funcionan tanto en **Termux (Android)** como en **Linux**.

## Modos de operación (daemon)

```bash
# Usa el modo definido en config.yaml (modo_operacion)
python3 main.py

# Forzar modo Automate File Broker (procesa archivos de notificaciones)
python3 main.py --broker

# Procesar un solo ciclo y salir (útil para pruebas)
python3 main.py --broker --once

# Forzar modo Listener Directo (SOLO Termux/Android)
python3 main.py --listener
```

> `--listener` requiere Termux. En Linux se rechaza con un mensaje claro;
> use `--broker` o el registro manual.

## Acciones de una sola ejecución

```bash
# Listar transacciones (tabla)
python3 main.py --accion listar

# Listar transacciones (JSON)
python3 main.py --accion listar --json

# Insertar transacción manual (con flags)
python3 main.py --accion insertar \
  --motivo "Motivo del movimiento" \
  --monto 15.50 \
  --tipo gasto \
  --destinatario "Beneficiario"

# Insertar de forma interactiva (si faltan --monto/--motivo)
python3 main.py --accion insertar

# Flujo interactivo completo (motivo, monto, destinatario, GPS, confirmación)
python3 main.py --accion registro
# (alias)
python3 main.py --registro

# Consultas SQL personalizadas
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5"
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5" --json

# Marcar las transacciones pendientes como sincronizadas
python3 main.py --accion sync

# Ver ayuda
python3 main.py --help
```

## Base de datos (resumen)

- Archivo SQLite en `config.yaml` → `bd.ruta_sqlite` (por defecto `./local_gastos.db`).
- **Guardado:** un único punto, `insertar_transaccion()`, usado por `--accion registro`,
  `--accion insertar` y los modos automáticos (`--broker`/`--listener`).
- **Listado:**
  - `--accion listar` → más recientes primero (recomendado).
  - `--accion sql "... LIMIT n"` **sin `ORDER BY`** → devuelve las **más antiguas**.
    Use `ORDER BY id DESC` para ver las recientes:
    ```bash
    python3 main.py --accion sql --sql "SELECT * FROM transacciones ORDER BY id DESC LIMIT 5" --json
    ```
- **Broker (`--broker`):** registra el JSON crudo en `notificaciones_crudas` (log
  tal cual), pide por consola/diálogo los datos faltantes (monto/tipo/destinatario/
  motivo) y **elimina `noti.json`** al terminar. Solo inserta en `transacciones` si
  cumple todas las reglas.
- Tablas: `transacciones` (movimientos), `notificaciones_crudas` (todo lo que ingresa),
  `abonos_prestamo` (abonos de préstamos: yo presté / me prestaron). Detalle en
  `README.md` → “Base de Datos”.
- Logs en consola y `./logs/app.log`.

## Notas

- La base de datos se resuelve desde `config.yaml` (`bd.ruta_sqlite`) y se crea
  automáticamente si no existe.
- Los proveedores (entrada, GPS, base de datos, notificaciones) se seleccionan
  automáticamente según el entorno: Termux usa las APIs nativas; Linux usa
  alternativas equivalentes (p. ej. geolocalización por IP para GPS).
- Todas las operaciones retornan el mismo sobre JSON:
  `{"code": 0|-1, "data": {...}, "valid": bool, "error": str|null}`.
