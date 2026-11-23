# C3 - IBK Adapter

## Descripción
Adapter principal para notificaciones Interbank y Plin.

### Soporte para formatos
- **TRAN**: Transferencias de gasto (formato: "TRAN S/ X.00\nA: Nombre")
- **PLIN**: Gastos Plin (formato: "Plineaste S/ X.00 a Nombre")
- **TARJETA**: Consumos con tarjeta (formato: "Realizaste un consumo con tu tarjeta.")
- **NFC**: Pagos con NFC/Wallet (formato: "S/ X.XX con Nombre ••NNNN")

### Manejo de duplicados
- **Mismo tipo NUNCA duplicado**: TRAN+TRAN, PLIN+PLIN, TARJETA+TARJETA, NFC+NFC
- **Tipos diferentes consolidan**: TRAN+PLIN, TRAN+TARJETA, TRAN+NFC, PLIN+TARJETA, PLIN+NFC, TARJETA+NFC

### Lógica de duplicados
- **Mismo tipo**: Siempre NUNCA es duplicado (mismos datos = transacciones distintas)
- **Tipos diferentes**: Consolidar si mismo destinatario + monto similar + ventana 5 min
- **Siempre se solicita motivo** via termux-dialog
- **Monto**: Solicitar solo para formato TARJETA (viene vacío en mensaje)

### Logging
- Archivo: `~/.local_gestion_gastos/app.log`
- Siempre se registra: inicio, acciones, errores, finalización

### Comandos
```bash
python3 main.py --accion listar
python3 main.py --accion insertar --motivo "..." --monto X --tipo gasto/ingreso --destinatario "..."
```

### Dependencias
- `pyyaml >= 6.0` (requirements.txt)
- `modulios/termux_api.py`
- `adaptadores/nfc.py`

### Versionamiento
- **Versión actual**: 2.0 (con soporte NFC y reglas de duplicados actualizadas)
- **Última actualización**: Noviembre 2026