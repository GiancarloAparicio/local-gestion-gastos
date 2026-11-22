# Agentes y Guía del Proyecto "local-gestion-gastos"

**Versión:** 1.0  
**Fecha:** 2026-11-21  
**Autor:** Usuario único (desarrollo y mantenimiento personal)  
**Entorno:** Ejecutado en OpenCode, backend con automatización Android

---

## 1. Propósito del Proyecto

Sistema de gestión de gastos e ingresos personales de forma local, con captura automática de notificaciones bancarias y respaldo offline. El frontend es **Automate en Android**, mientras que el backend procesa los datos y los sincroniza a la nube (Google Sheets + Looker Studio).

### Objetivos principales:
- Capturar transacciones en tiempo real desde notificaciones de bancos
- Solicitar el motivo de cada movimiento al usuario
- Almacenar datos en SQLite local (modo offline-first)
- Sincronizar con Google Cloud Functions y Google Sheets
- Permitir visualización de KPIs en Looker Studio

---

## 2. Público

- **Propietario y único desarrollador:** Yo mismo
- **No hay equipo externo ni contribuciones externas esperadas**
- El documento está pensado para mi propio referencia y mantenimiento futuro

---

## 3. Convenciones y Buenas Prácticas

### 3.1 Idioma de los comentarios
- **Todos los comentarios de código deben estar en español** para facilitar la comprensión de la lógica de negocio.
- Los nombres de variables y funciones pueden ser en inglés (convención estándar), pero sus descripciones y comentarios deben ser en español.

### 3.2 Estructura de archivos
- **Un solo archivo por funcionalidad máxima.** Cada archivo debe encargarse de una sola responsabilidad.
- **Máximo dos archivos relacionados** si es necesario dividir lógicamente una funcionalidad (ej. un script de procesamiento y su configuración).
- **Nombres de archivos descriptivos y en español** cuando sea posible (ej. `procesar_notificaciones.py`, `solicitar_motivo.py`).

### 3.3 Patrones de arquitectura

#### 3.3.1 Patrón Offline-First
- La base de datos SQLite local es la **fuente única de verdad** (ver diagrama Entidad-Relación en `doc/Diagrama-BD.uml`).
- Los datos se sincronizan a la nube cuando hay conexión a internet.
- El modo offline debe funcionar completamente sin conexión.

#### 3.3.2 Patrón FIFO (Cola de Prioridad)
- Las notificaciones crudas se procesan en orden FIFO (ver entidad `notificaciones_crudas` en diagrama BD).
- Se aplica anti-duplicado antes de insertar en la tabla principal de transacciones.

#### 3.3.3 Patrón Adaptador por Banco
- Cada banco tiene su propio adaptador de notificaciones (ver `doc/C3-IBKAdapter.uml`, `doc/C3-BBVAAdapter.uml`).
- Los adaptadores comparten flujo común pero difieren en el parser de notificaciones.
- **Nuevo banco:** Si se añade un nuevo adaptador, seguir el patrón de los existentes.

#### 3.3.4 Patrón Solicitud de Usuario (User Prompt)
- Después de detectar una notificación, se **siempre** debe solicitar el motivo al usuario vía `termux-dialog`.
- El flujo es obligatorio: notificación → solicitud de motivo → GPS (opcional) → guardar en SQLite → sincronizar a nube.

### 3.4 Buenas prácticas de código

1. **Validación temprana:** Validar el tipo de movimiento (ingreso/gasto) y monto antes de proceder.
2. **Manejo de timeouts:** Todos los procesos de dialog y GPS deben tener timeouts definidos para evitar bloqueos.
3. **Respaldo de seguridad:** La tabla `notificaciones_crudas` es la auditoría de la cola FIFO; nunca debe perderse.
4. **Event ID único:** Cada transacción debe tener un `event_id` único para rastreo y anti-duplicado.
5. **Estado synchronized:** Cada registro debe tener el campo `synced` (0 = pendiente, 1 = sincronizado) para controlar el estado de sincronización.

---

## 4. Estructura del Proyecto

Basado en la arquitectura C4 (ver `doc/C1-Gestion-Gastos.uml` y `doc/C2-Gestion-Gastos.uml`):

### 4.1 Entorno Móvil (Android - Local)
```
automate/   - Sensor de notificaciones (App Automate)
termux/     - Motor de procesamiento (Python/scripts)
dialog_api/ - Gestión de interfaces locales (termux:API)
sqlite/     - Base de datos local offline
```

### 4.2 Entorno Cloud (Backend)
```
api/        - API de Google Cloud Function (Python)
sheets/     - Google Sheets (historial definitivo)
looker/     - Looker Studio (visualización KPIs)
```

### 4.3 Flujo de datos
```
Banco → Notificación Push → Automate → Termux → Dialog (motivo + monto) → SQLite → API Cloud → Google Sheets → Looker Studio
```

---

## 5. Patrones Específicos por Componente

### 5.1 Procesador de Notificaciones (Termux/Python)
- Cada notificación debe ser enrutada a su adaptador correspondiente (IBK, BBVA, etc.).
- Flujo común:
  1. Validar que sea notificación de banco válida
  2. Parsear datos (monto, destinatario, tipo)
  3. Verificar anti-duplicado en SQLite
  4. Solicitar motivo al usuario
  5. Obtener GPS (con fallback a última conocida)
  6. Insertar en SQLite con `status = consolidated, synced = 0`
  7. Si hay internet: enviar a API Cloud

### 5.2 API Google Cloud Function (Python)
- Recibir payload JSON desde el móvil.
- Validar esquema y `event_id`.
- Insertar/actualizar registros en Google Sheets.
- Retornar respuesta 2xx o error adecuado.

### 5.3 Sincronización Offline → Online
- Verificar campo `synced` antes de reenviar.
- En caso de fallo de red, mantener `synced = 0` y reintentar próximo ciclo.
- Lógica de reintento exponencial opcional.

---

## 6. Guía para Nuevos Agentes o Scripts

Si se quiere añadir nueva funcionalidad:

1. **Un solo propósito por script.** Ej: `script_obtener_gps.py`, `script_validar_anti_duplicado.py`.
2. **Comentarios en español.** Documentar la lógica de negocio.
3. **Seguir el flujo establecido:**
   - Entrada: notificación o dato crudo
   - Procesamiento: validación, parsing, GPS, usuario
   - Salida: inserción en SQLite + optional sync a nube
4. **Nombres de funciones claros** en español o inglés con documentación en español.
5. **Probar modo offline** antes de desplegar cambios.
6. **Verificar adaptadores existentes** antes de crear uno nuevo para un banco no contemplado.

---

## 7. Recursos y Referencias

- `doc/C1-Gestion-Gastos.uml` - Diagrama de Contexto (Nivel 1)
- `doc/C2-Gestion-Gastos.uml` - Diagrama de Contenedores (Nivel 2)
- `doc/Diagrama-BD.uml` - Modelo de Base de Datos SQLite
- `doc/C3-IBKAdapter.uml` - Adaptador Interbank (procesos de transferencia)
- `doc/C3-BBVAAdapter.uml` - Adaptador BBVA (ingresos y gastos generales)
- `doc/C3-Gestion-Gastos.pdf` - Resumen visual del proceso general

---

## 8. Checklist de Buenas Prácticas (por archivo)

Para cada nuevo archivo/script creado:

- [ ] Comentarios principales en español (lógica de negocio)
- [ ] Nombre de archivo descriptivo (máx. 3-4 palabras)
- [ ] Una sola funcionalidad principal
- [ ] Validaciones de entrada incluidas
- [ ] Manejo de timeouts en procesos externos (GPS, dialog)
- [ ] Guardado en SQLite con campos `status` y `synced`
- [ ] Caso de modo offline considerado
- [ ] Posibilidad de sincronización a la nube
- [ ] Arquitectura con wrappers/adaptadores para facilitar cambios futuros

---
## 9. Abstracción y Wrappers para Facilidad de Cambio

El objetivo de esta sección es asegurar que el sistema esté diseñado para ser fácilmente modificable en el futuro, siguiendo el principio de **Inversión de Dependencias** y **Programación contra Interfaces**, no contra implementaciones concretas.

### 9.1 Principio de Dependencia Invertida (DDI)
- **No depender de detalles**, sino de abstracciones.
- Los módulos de alto nivel (lógica de negocio, flujo de trabajo) no deben depender de módulos de bajo nivel (SQLite, Google Cloud Functions). Ambos deben depender de abstracciones comunes.
- Esto permite cambiar la implementación concreta sin afectar la lógica de negocio.

### 9.2 Capa de Abstracción de Base de Datos
- **Definir una interfaz/contrato** para las operaciones de base de datos (ej. `GuardarTransaccion`, `ObtenerTransacciones`, `ActualizarSincronizacion`).
- **Implementación actual:** SQLite (`sqlite/` folder) con las tablas definidas en `doc/Diagrama-BD.uml`.
- **Implementaciones futuras posibles:**
  - PostgreSQL con controlador `psycopg2` o `asyncpg`
  - MySQL con controlador `pymysql`
  - Arquitectura de archivo plano si es necesario
- **Cómo cambiar:** Solo se necesita crear una nueva clase/implementación de la interfaz y actualizar el wiring de dependencias; la lógica de negocio permanece intacta.

### 9.3 Adaptadores de Servicios en la Nube (API Wrapper)
- **API Google Cloud Function actual:** `api/` folder con Python.
- **Wrapper/Interfaz definida** con métodos como:
  - `EnviarTransaccion(payload: dict) -> dict`
  - `VerificarEstadoSincronizacion(event_id: str) -> bool`
  - `ObtenerHistorial(filters: dict) -> list`
- **Implementaciones posibles:**
  - Cambiar a AWS Lambda con patrónsimilar
  - Cambiar a Azure Functions
  - Cambiar a un servidor Node.js/Express propio
  - Cambiar a un servicio de terceros (Firebase Functions, etc.)
- **Cómo cambiar:** Implementar la interfaz para el nuevo proveedor y actualizar la configuración de endpoints; el código que llama a la API sigue usando los mismos nombres de método.

### 9.4 Adaptadores de Notificaciones por Banco (Patrón ya existente)
- **Ya implementado** en `doc/C3-IBKAdapter.uml` y `doc/C3-BBVAAdapter.uml`.
- **Principio:** Cada banco tiene su propio adaptador que convierte el formato crudo de la notificación a un formato interno normalizado.
- **Futuro:** Si se quiere agregar un nuevo banco (ej. Nubank, Chase, etc.), se crea un nuevo adaptador siguiendo el patrón existente sin tocar el procesador central.
- **Interfaz común:** Todos los adaptadores deben cumplir con el contrato de retornar un diccionario normalizado con: `monto`, `tipo`, `destinatario`, `event_id`, `fecha_hora`.

### 9.5 Flujo de Inyección de Dependencias (Simplificado)
Para mantener la facilidad de cambio, el flujo típico en los scripts de Termux/Python sería:

1. **Configuración centralizada:** Un archivo de configuración (ej. `config.py`) define qué adaptador/basedatos/API se está usando.
2. **Instanciación:** Los módulos reciben sus dependencias por parámetro o las obtienen del configurador.
3. **Interfaz común:** Siempre se llama al mismo nombre de método, independientemente de la implementación subyacente.

#### Ejemplo conceptual (Python):

```python
# Interfaz/contrato base (siempre se usa esto)
from abc import ABC, abstractmethod

class DatabaseAdapter(ABC):
    @abstractmethod
    def guardar_transaccion(self, datos: dict) -> str:
        pass
    
    @abstractmethod
    def actualizar_sincronizacion(self, event_id: str, status: str) -> None:
        pass

# Implementación actual (SQLite)
class SQLiteAdapter(DatabaseAdapter):
    def guardar_transaccion(self, datos: dict) -> str:
        # INSERT INTO transacciones ...
        return event_id
    
    def actualizar_sincronizacion(self, event_id: str, status: str) -> None:
        # UPDATE transacciones SET synced = ... WHERE event_id = ...

# Implementación futura (PostgreSQL)
class PostgreSQLAdapter(DatabaseAdapter):
    def guardar_transaccion(self, datos: dict) -> str:
        # INSERT INTO transacciones ... usando psycopg2
        return event_id
    
    def actualizar_sincronizacion(self, event_id: str, status: str) -> None:
        # UPDATE transacciones ... usando psycopg2

# Uso en el código principal (nunca llama directo a SQLite ni psql)
def procesar_notificacion(adapter: DatabaseAdapter, datos: dict):
    event_id = adapter.guardar_transaccion(datos)
    # ... resto de lógica
    adapter.actualizar_sincronizacion(event_id, "consolidado")
```

### 9.6 Beneficios de esta Abstracción
- **Cambio de base de datos:** De SQLite a PostgreSQL/MySQL en minutos, solo cambiando la implementación del adaptador.
- **Cambio de API en la nube:** De Google Cloud Functions a AWS/Azure/Firebase con mínimo impacto.
- **Agregar nuevos bancos:** Crear un nuevo adaptador siguiendo el patrón, sin modificar el flujo central.
- **Testing más fácil:** Se pueden crear "falsas" implementaciones (mocks) de la interfaz para testing unitario sin necesidad de SQLite o API reales.
- **Futuro-proof:** El sistema puede evolucionar tecnológicamente sin necesidad de reescribir la lógica de negocio completa.

### 9.7 Checklist de Implementación de Wrappers
Para cada nuevo módulo o componente agregado:

- [ ] Definir interfaz/contrato clara (archivo separado, ej. `db_interfaces.py`, `api_interfaces.py`)
- [ ] Implementación actual debe cumplir la interfaz
- [ ] Inyección de dependencias (pasar el adaptador por parámetro o configurador)
- [ ] No hardcodear nombres de clases concretas en la lógica de negocio
- [ ] Documentar la interfaz con ejemplos de uso
- [ ] Probar con al menos una implementación alternativa (o mock) antes de considerar el módulo listo

---
*Última actualización: 2026-11-21*
