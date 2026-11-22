# C3 - Yape Adapter

## Descripción
Adapter para notificaciones de Yape (banco/billetera digital).

### Características
- Soporte para notificaciones de Yape (Banco/Billetera digital)
- Integración con el sistema de validación de duplicados
- Almacenamiento en base de datos SQLite

### Formatos soportados
- Formatos específicos de notificaciones Yape
- Posible compatibilidad con formatos estándar (TRAN, PLIN) dependiendo de la estructura del mensaje

### Comandos relacionados
```bash
python3 main.py --accion listar
python3 main.py --accion insertar
```

### Integración con el sistema
- El adapter Yape hereda de la misma base que IBK
- Validación de duplicados consistente con las reglas del sistema
- Logging consistente en `~/.local_gestion_gastos/app.log`
