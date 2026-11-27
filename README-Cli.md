# local-gestion-gastos - CLI

## Comandos Disponibles

```bash
# Ver transacciones (formato tabla)
python3 main.py --accion listar

# Ver transacciones (formato JSON)
python3 main.py --accion listar --json

# Insertar transacción manual
python3 main.py --accion insertar \
  --motivo "Motivo del movimiento" \
  --tipo gasto/ingreso \
  --monto 15.50 \
  --destinatario "Nombre del beneficiario"

# Consultas SQL personalizadas
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5"

# Consultas SQL en formato JSON
python3 main.py --accion sql --sql "SELECT * FROM transacciones LIMIT 5" --json

# Ver ayuda
python3 main.py --help
```