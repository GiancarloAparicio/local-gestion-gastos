# C3 - Plin Adapter

## Descripción
Adapter para procesar notificaciones PLIN (Pagos P2P).

### Características
- Procesar notificaciones PLIN (Pagos P2P)
- Validar duplicados (mismo tipo NUNCA duplicado)
- Almacenar en base de datos SQLite
- Solicitar motivo via termux-dialog

### Lógica de duplicados para PLIN
- **Mismo tipo PLIN + PLIN: NUNCA duplicado** (mismos datos = eventos independientes)
- **PLIN + TRAN/TARJETA/NFC**: Consolidar si mismo destinatario + monto similar + ventana 5 min
- **Siempre solicitar motivo** via termux-dialog

### Flujo de procesamiento
1. Recibir notificación PLIN
2. Clasificar formato PLIN
3. Validar duplicados (mismo tipo NUNCA duplicado)
4. Si es duplicado: consolidar con registro existente
5. Si no es duplicado: insertar nuevo registro
6. Solicitar motivo via termux-dialog

### Comandos
```bash
python3 main.py --accion listar
python3 main.py --accion insertar --motivo "..." --monto X --tipo gasto --destinatario "..."
```

### Integración con el sistema
- El adapter PLIN hereda de la misma base que IBK
- Validación de duplicados consistente con las reglas del sistema
- Logging consistente en `~/.local_gestion_gastos/app.log`

### Versionamiento
- **Versión actual**: 2.0 (con reglas de duplicados actualizadas)
- **Última actualización**: Noviembre 2026