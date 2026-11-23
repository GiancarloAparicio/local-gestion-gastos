# C3 - Gastos e Ingresos Manuales Adapter

## Descripción
Adapter para ingresos y gastos manuales registrados mediante la CLI del sistema.

### Características
- Registro manual de transacciones
- Validación de tipo (gasto/ingreso)
- Solicitud de motivo via línea de comandos
- Almacenamiento en base de datos SQLite

### Flujo de trabajo
1. Ejecutar: `python3 main.py --accion insertar --motivo "..." --monto X --tipo gasto/ingreso --destinatario "..."`
2. Validar parámetros
3. Insertar en base de datos SQLite
4. Actualizar log de actividades
5. Retornar confirmación con event_id

### Dependencias
- `adaptadores/infraestructura/sqlite_adapter.py`
- `modulios/termux_api.py`
- `main.py`

### Comandos de ejemplo
```bash
python3 main.py --accion insertar --motivo "Pago servicios" --monto 50.00 --tipo gasto --destinatario "Empresa X"
python3 main.py --accion listar
```