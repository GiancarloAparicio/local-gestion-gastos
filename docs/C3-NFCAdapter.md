# C3 - NFC Adapter

## Descripción
Adapter para procesar notificaciones NFC y Google Pay.

### Características
- Procesar notificaciones NFC (Google Pay / Wallet)
- Extraer monto, beneficiario, tipo_consumo
- Solicitar motivo via termux_api con contexto NFC
- Almacenar en base de datos SQLite

### Lógica de duplicados para NFC
- **Mismo tipo NFC + NFC: NUNCA duplicado** (mismos datos = pagos independientes)
- **NFC + TRAN/TARJETA/PLIN**: Consolidar si mismo destinatario + monto similar + ventana 5 min
- **Siempre solicitar motivo** via termux_api.solicitar_motivo_contexto

### Flujo de procesamiento
1. Recibir notificación NFC (walletnfcrel)
2. Extraer monto, beneficiario, tipo_consumo
3. Validar duplicados (mismo tipo NUNCA duplicado)
4. Si es duplicado: consolidar con registro existente
5. Si no es duplicado: insertar nuevo registro
6. Solicitar motivo via termux_api con contexto NFC

### Comandos
```bash
python3 main.py --accion listar
python3 main.py --accion insertar --motivo "..." --monto X --tipo gasto --destinatario "..."
```

### Integración con el sistema
- El adapter NFC hereda de la misma base que IBK
- Validación de duplicados consistente con las reglas del sistema
- Logging consistente en `~/.local_gestion_gastos/app.log`

### Versionamiento
- **Versión actual**: 2.0 (con reglas de duplicados actualizadas)
- **Última actualización**: Noviembre 2026