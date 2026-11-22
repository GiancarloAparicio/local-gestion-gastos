# C3 - Compartamos Adapter

## Descripción
Adapter para notificaciones del servicio Compartamos (Servicios Financieros).

### Características
- Soporte para notificaciones específicas de Compartamos
- Integración con el sistema de validación de duplicados
- Almacenamiento en base de datos SQLite

### Formatos soportados
- Formatos específicos de notificaciones Compartamos
- Posible compatibilidad con formatos estándar (TRAN, PLIN) dependiendo de la estructura del mensaje

### Comandos relacionados
```bash
python3 main.py --accion listar
python3 main.py --accion insertar
```

### Integración con el sistema
- El adapter Compartamos hereda de la misma base que IBK
- Validación de duplicados consistente con las reglas del sistema
- Logging consistente en `~/.local_gestion_gastos/app.log`
