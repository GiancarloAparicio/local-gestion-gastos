# C3 - Gestion Gastos

## Visão geral do sistema
Sistema de gestión de gastos e ingresos para Android/Termux que procesa notificaciones bancarias.

### Formatos soportados
- **TRAN**: Transferencias bancarias (formato: "TRAN S/ X.00\nA: Nombre")
- **PLIN**: Pagos P2P (formato: "Plineaste S/ X.00 a Nombre")
- **TARJETA**: Consumos con tarjeta (formato: "Realizaste un consumo con tu tarjeta.")
- **NFC**: Google Pay / Wallet (formato: "S/ X.XX con Nombre ••NNNN")

### Reglas de duplicados (NUEVO)
- **Mismo tipo NUNCA es duplicado**: TRAN+TRAN, PLIN+PLIN, TARJETA+TARJETA, NFC+NFC
- **Tipos diferentes SÍ consolidan**: Cualquier combinación de tipos diferentes si comparten mismo destinatario + monto similar + ventana 5 min

### Flujo de procesamiento
1. Recibir notificación
2. Clasificar formato (TRAN, PLIN, TARJETA o NFC)
3. Validar duplicados
4. Si es duplicado: consolidar con registro existente
5. Si no es duplicado: insertar nuevo registro
6. Siempre solicitar motivo via termux-dialog (excepto si ya fue solicitado anteriormente)

### Archivos clave
- `adaptadores/ibk.py`: Lógica principal de clasificación y duplicados
- `adaptadores/nfc.py`: Soporte NFC
- `modulios/termux_api.py`: GPS y diálogos
- `main.py`: CLI principal

### Comandos
```bash
bash instalacion.sh  # Instalar entorno
python3 main.py --accion listar  # Ver transacciones
python3 main.py --accion insertar --motivo "..." --monto X --tipo gasto --destinatario "..."  # Insertar
```