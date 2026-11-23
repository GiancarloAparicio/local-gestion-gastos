# C3 - IBK Tarjeta Adapter

## Descripción
Adapter para procesar notificaciones de consumos con tarjeta.

### Características
- Procesar notificaciones de consumos con tarjeta
- Validar duplicados (mismo tipo NUNCA duplicado)
- Solicitar motivo y monto (monto viene vacío en el mensaje)
- Almacenar en base de datos SQLite

### Flujo de procesamiento
1. Recibir notificación de tarjeta
2. Clasificar formato TARJETA
3. Monto viene vacío en el mensaje → Solicitar al usuario
4. Validar duplicados (mismo tipo NUNCA duplicado, tipos diferentes consolidan)
5. Insertar/Actualizar en base de datos SQLite
6. Retornar confirmación con event_id

### Lógica de duplicados para TARJETA
- **Mismo tipo TARJETA + TARJETA: NUNCA duplicado**
- **TARJETA + TRAN/PLIN/NFC**: Consolidar si mismo destinatario + monto similar + ventana 5 min
- **Siempre solicitar motivo** via termux-dialog (a menos que ya fue solicitado anteriormente)

### Comandos
```bash
python3 main.py --accion listar
python3 main.py --accion insertar --motivo "..." --monto X --tipo gasto --destinatario "..."
```

### Dependencias
- `adaptadores/ibk.py`: Lógica principal
- `modulios/termux_api.py`: Diálogos y solicitud de monto
- `main.py`: Punto de entrada

### Versionamiento
- **Versión actual**: 2.0 (con reglas de duplicados actualizadas)
- **Última actualización**: Noviembre 2026