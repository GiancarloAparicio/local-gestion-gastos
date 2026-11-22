# C1 - Arquitectura General - local-gestion-gastos

## Arquitectura del sistema local-gestion-gastos

### Componentes principales
- **USUARIO**: Interacciones a través de la línea de comandos (CLI)
- **MAIN PYTHON**: Punto de entrada principal (main.py)
- **ADAPTADORES**: Módulos de procesamiento (IBK, NFC, BBVA, Yape, etc.)
- **MODULIOS**: Módulos auxiliares (termux_api, logger, consolidador, validador, fifo_cola)
- **BASE DATOS SQLite**: Almacenamiento de transacciones (local_gastos.db)
- **LOGS**: Registro de actividades (logs/app.log)

### Flujo de datos
```
USUARIO --> MAIN PYTHON --> ADAPTADORES --> BASE DATOS SQLite
                 --> MODULIOS --> Validaciones y utilidades
BASE DATOS SQLite --> LOGS --> Reportes y vistas de usuario
```

### Componentes principales

#### main.py
Punto de entrada del sistema. Gestiona:
- Comandos `listar` y `insertar`
- Validación de parámetros
- Llamada a adaptadores y módulos
- Actualización de base de datos
- Escritura de logs

#### Adaptadores (adaptadores/)
- `ibk.py`: Procesador principal para IBK/Interbank
- `nfc.py`: Procesador para notificaciones NFC/Google Pay
- `bbva.py`, `compartamos.py`, `yape.py`, `manual.py`: Adapters específicos

#### Módulos (modulios/)
- `termux_api.py`: GPS, diálogos, utilidades del sistema
- `logger.py`: Logging centralizado
- `consolidador.py`: Lógica de consolidación de transacciones
- `validador.py`: Validación de datos y formatos
- `fifo_cola.py`: Cola de procesamiento de notificaciones

### Configuración
- `config.yaml`: Configuración del sistema
- `requirements.txt`: Dependencias (pyyaml)
- `instalacion.sh`: Script de instalación y configuración

### Logging
- Archivo de log: `~/.local_gestion_gastos/app.log`
- Formato: `[TIMESTAMP] NIVEL - MENSAJE`
- Niveles: INFO, WARNING, ERROR, CRITICAL
- Siempre registra: inicio, acciones, errores, finalización

### Comandos principales
```bash
# Instalar/Configurar
bash instalacion.sh

# Ver transacciones
python3 main.py --accion listar

# Insertar transacción manual
python3 main.py --accion insertar \
  --motivo "Motivo" \
  --monto X \
  --tipo gasto/ingreso \
  --destinatario "Nombre"

# Ver logs
cat ~/.local_gestion_gastos/app.log
```

### Formatos de notificación soportados
- **TRAN**: Transferencias bancarias - "TRAN S/ X.00\\nA: Nombre"
- **PLIN**: Pagos P2P - "Plineaste S/ X.00 a Nombre"
- **TARJETA**: Consumos con tarjeta - "Realizaste un consumo con tu tarjeta."
- **NFC**: Google Pay - "S/ X.XX con Nombre ••NNNN"

### Reglas de duplicados (NUEVO)
- **Mismo tipo NUNCA duplicado**: TRAN+TRAN, PLIN+PLIN, TARJETA+TARJETA, NFC+NFC
- **Tipos diferentes SÍ consolidan**: Cualquier combinación de tipos diferentes si comparten mismo destinatario + monto similar + ventana 5 min

### Versionamiento
- **Versión actual**: 2.0 (con soporte NFC y reglas de duplicados actualizadas)
- **Última actualización**: Noviembre 2026
