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

```bash
# Instalar entorno
bash instalacion.sh

# Ver transacciones (formato tabla)
python3 main.py --accion listar

# Ver transacciones (formato JSON)
python3 main.py --accion listar --json

# Insertar transacción manual
python3 main.py --accion insertar \
  --motivo "Motivo del movimiento" \
  --monto 15.50 \
  --tipo gasto \
  --destinatario "Beneficiario"

# Consultas SQL personalizadas
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5"

# Consultas SQL en formato JSON
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5" --json

# Ver ayuda
python3 main.py --help
```

## Documentación
- `docs/`: Diagramas UML y documentación PDF