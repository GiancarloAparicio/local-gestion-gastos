# local-gestion-gastos - CLI

## Comandos Disponibles

```bash
# Ver transacciones
python3 main.py --accion listar

# Insertar transacción manual
python3 main.py --accion insertar \
  --motivo "Motivo del movimiento" \
  --tipo gasto/ingreso \
  --monto 15.50 \
  --destinatario "Nombre del beneficiario"

# Ver ayuda
python3 main.py --help
```
