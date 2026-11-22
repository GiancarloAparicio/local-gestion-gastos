# C2 - Gestion de Gastos

## Flujo de Trabajo de Procesamiento de Notificaciones

### Estado actual del sistema
El sistema procesa notificaciones de 4 formatos: TRAN, PLIN, TARJETA, NFC.

### Reglas de duplicados (NUEVO)
- **Mismo tipo NUNCA duplicado**: TRAN+TRAN, PLIN+PLIN, TARJETA+TARJETA, NFC+NFC
- **Tipos diferentes SÍ consolidan**: Cualquier combinación de tipos diferentes si comparten mismo destinatario + monto similar + ventana 5 min

### Flujo de trabajo paso a paso
1. **NOTIFICACIÓN RECIBIDA**: Llegada de notificación del sistema Automate o directo
2. **VALIDAR PAQUETE**: Verificar que sea paquete conocido (IBK, NFC, Yape, etc.)
3. **CLASIFICAR FORMATO**: Determinar si es TRAN, PLIN, TARJETA o NFC
4. **PROCESAR**: Aplicar lógica según el formato clasificado
5. **SOLICITAR MOTIVO**: Siempre se solicita motivo via termux-dialog
6. **VALIDAR DUPLICADOS**: Aplicar reglas de duplicados (mismo tipo NUNCA, tipos diferentes SÍ)
7. **CONSOLIDAR O INSERTAR**: Insertar nuevo o consolidar con existente
8. **FIN**: Registro completado en SQLite

### Estados de proceso
- **NUEVO**: Primera notificación de un gasto/ingreso
- **CONSOLIDADO**: Notificación que complementa a una existente (mismo gasto, formato diferente)
- **IGUAL TIPO**: Mismo tipo de notificación = registro independiente (no es duplicado)

### Comandos de ejemplo
```bash
# Ver transacciones
python3 main.py --accion listar

# Insertar manual
python3 main.py --accion insertar --motivo "Pago" --monto 20.50 --tipo gasto --destinatario "Empresa"

# Ver logs
cat ~/.local_gestion_gastos/app.log
```
