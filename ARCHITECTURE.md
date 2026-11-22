# Arquitectura del Sistema "local-gestion-gastos"

Arquitectura C4 + Arquitectura Hexagonal (Ports and Adapters)  
Sistema de gestión de gastos e ingresos personales offline-first  
Frontend: Automate en Android | Backend: Termux/Python + Google Cloud Functions  
Última actualización: 2026-11-21

---

## 1. Visión General (C4 Nivel 1)

### 1.1 Actor Principal
- **Usuario:** Realiza pagos/ingresos, clasifica motivos, analiza su presupuesto  
- **Casos de uso principales:**
  - Capturar transacciones desde notificaciones bancarias
  - Solicitar motivo de movimiento (obligatorio, via termux-dialog)
  - Capturar ubicación geográfica (GPS con respaldo offline)
  - Almacenar y consultar historial de gastos/ingresos en SQLite local
  - Sincronizar con nube para análisis en Looker Studio

### 1.2 Sistemas Externos
- **Bancos y billeteras digitales:**
  - Yape (billetera digital - ingresos)
  - Plin (transferencias interbancarias - ingresos y gastos)
  - BBVA (banco - notificaciones genéricas, requiere prompt guiado)
  - Interbank (transferencias - gastos)
  - NFC (pagos sin contacto/unificados con tarjeta)
  - Compartamos Financiera (crédito - solo ingresos)
- **Automate (Android):** App de automatización que intercepta notificaciones push y puede entregar archivos al broker de Termux
- **Google Sheets:** Base de datos en la nube, historial definitivo, mirror de datos locales
- **Looker Studio:** Consumo de datos Sheets, tableros KPIs, gráficos y reportes financieros
- **Google Cloud Function:** API intermedia que recibe payloads JSON y realiza inserción/actualización idempotente en Sheets

### 1.3 Frontera del Sistema (Boundaries)
La frontera se divide en dos capas principales:

**Capa Móvil (Local/Offline-First):**
- Aplicación Automate en Android
- Entorno Termux con Python como motor de procesamiento
- Base de datos SQLite local (3 tablas: transacciones, notificaciones_crudas, abonos_prestamo)
- GPS del dispositivo (termux-location)
- Diálogos termux-dialog para interacción obligatoria con usuario

**Capa Cloud (Backend):**
- Google Cloud Functions (Python) - recepción y validación de payloads
- Google Sheets (almacenamiento en nube, fuente para Looker)
- Looker Studio (visualización KPIs y reportes)

---

## 2. Visión de Contenedores (C4 Nivel 2)

### 2.1 Contenedores Definidos

| Contenedor | Tecnología | Responsabilidad Clave |
|------------|------------|------------------------|
| **automate** | App Android (Automate) | Sensor de notificaciones FIFO, modo broker (archivos) o listener directo |
| **termux** | Termux + Python | Motor de procesamiento orquestador, lógica de negocio, todos los adaptadores |
| **sqlite** | SQLite (archivo local) | Base de datos offline-first, persistencia sin internet necesario |
| **api** | Google Cloud Function (Python) | Recibe payload JSON validado, inserción/actualización idempotente en Sheets |
| **sheets** | Google Sheets | Almacenamiento en nube, mirror exacto de datos locales, fuente Looker Studio |
| **looker** | Looker Studio | Visualización de KPIs, gráficos de gastos/ingresos/préstamos/ubicación |

### 2.2 Relaciones y Flujo entre Contenedores

```
+---------------------+     +----------------------+     +----------------------+
|      USER           |     |     AUTOMATE         |     |  GOOGLE CLOUD        |
+---------------------+     +----------------------+     +----------------------+
       |                        |                              |
       | 1. Notificación Push   |                              |
       |--------------------->|                              |
       |                        | 2. Escribe archivo FIFO      |
       |                        |----------------------------->|
       |                        |          TERMINUX            |
       |                        | 3. Detecta archivo nuevo     |
       |                        |----------------------------->|
       |                        | 4. Procesa pipeline completo |
       |                        |   → adaptador → GPS → dialog |
       |                        |   → SQLite → payload        |
       |                        |----------------------------->|
       |                        |          API CLOUD          |
       |                        | 5. Recibe payload JSON      |
       |                        | 6. Validar esquema          |
       |                        | 7. Insertar/Actualizar      |
       |                        |    Sheets (idempotente)     |
       |                        |----------------------------->|
       |                        |          GOOGLE SHEETS      |
       |                        | 8. Datos actualizados       |
       |                        |----------------------------->|
       |                        |          LOOKER STUDIO      |
                              | 9. KPIs, gráficos, reportes|
```

### 2.3 Modos de Operación entre Contenedores

**Modo A - Automate File Broker (modo principal actual):**
```
Automate (Android)
  ↓ deja archivo en directorio configurado
Termux/Python (Service Broker)
  ↓ invoca procesador con ruta archivo
SQLite local ←→ Procesamiento → API Cloud → Sheets → Looker
```

**Modo B - Listener Directo (modo alternativo):**
```
Termux/Python (bucle while)
  ↓ captura notificaciones nativas directamente
SQLite local ←→ Procesamiento inmediato → API Cloud → Sheets → Looker
```

---

## 3. Visión de Componentes (C4 Nivel 3)

La Arquitectura Hexagonal (Ports and Adapters) está aplicada en la capa de `termux`/`Python`, separando la lógica de negocio pura de los detalles de implementación.

### 3.1 Capa de Dominio (Business Logic Pure)

Entidades sin dependencias externas:

1. **`Transaccion`** - Movimiento financiero consolidado
   - Atributos clave: id_transaccion, fecha_hora, tipo (ingreso/gasto), monto, moneda, destinatario, motivo, categoria, medio
   - Atributos de préstamo: es_prestamo, monto_pagado, saldo_pendiente, estado_prestamo (activo/parcial/saldado)
   - Atributos ubicación: latitud, longitud, gps_source (live/last_known/none), mapa_url
   - Atributos control: status (consolidado), sincronizado (0/1), intentos_sync, ultimo_error_sync

2. **`NotificacionCruda`** - Notificación recibida tal cual del banco
   - Atributos: id, recibido_en, paquete, app, dispositivo, titulo, cuerpo, id_transaccion_vinculada, resultado_proceso

3. **`AbonoPrestamo`** - Historial de pagos parciales a deudas
   - Atributos: id, id_transaccion_prestamo, id_transaccion_ingreso, fecha_abono, monto_abono, saldo_restante, nota

### 3.2 Puertos (Interfaces de Contrato)

Definiciones de contrato que la lógica de negocio usará (archivos en `puertos/`):

#### Puerto: `NotificacionListener` (Modo de captura)
```python
from abc import ABC, abstractmethod

class NotificacionListener(ABC):
    @abstractmethod
    def capturar_notificacion(self, datos_crudos: dict) -> dict:
        """Capturar notificación y retornar diccionario normalizado."""
        pass
    
    @abstractmethod
    def es_modo_activado(self) -> bool:
        """Verificar si este modo de captura está activo."""
        pass
```

**Implementaciones concretas:**
- `EstrategiaAutomateBroker`: Lee archivo dejado por Automate en directorio configurado
- `EstrategiaListenerDirecto`: Bucle while capturando notificaciones nativas via API Android

#### Puerto: `DatabaseAdapter` (Persistencia)
```python
class DatabaseAdapter(ABC):
    @abstractmethod
    def guardar_transaccion(self, transaccion: Transaccion) -> str:
        """Guardar transacción, retorna event_id."""
        pass
    
    @abstractmethod
    def obtener_ultima_ubicacion(self) -> dict|None:
        """Obtener última ubicación válida registrada."""
        pass
    
    @abstractmethod
    def actualizar_sincronizacion(self, event_id: str, status: str) -> None:
        """Actualizar campo synced de una transacción."""
        pass
    
    @abstractmethod
    def verificar_duplicado_ventana(self, datos: dict) -> bool:
        """Verificar si existe registro similar en ventana de consolidación."""
        pass
```

**Implementaciones:**
- `SQLiteAdapter`: Usa las 3 tablas definidas en Diagrama-BD.uml
- `PostgreSQLAdapter`: Futuro, misma interfaz, driver psycopg2

#### Puerto: `GPSProvider` (Ubicación)
```python
class GPSProvider(ABC):
    @abstractmethod
    def obtener_ubicacion(self) -> dict|None:
        """Retornar dict con lat, lng, gps_source o None si falla."""
        pass
    
    @abstractmethod
    def ultimo_conocido(self) -> dict|None:
        """Retornar última ubicación guardada en SQLite."""
        pass
```

**Implementaciones:**
- `GPSTermuxLive`: Ejecuta `termux-location` con timeout, usa resultado actual
- `GPSCacheSQLite`: Busca última ubicación válida en historial

#### Puerto: `DialogProvider` (Interacción usuario)
```python
class DialogProvider(ABC):
    @abstractmethod
    def solicitar_motivo(self, pregunta: str, timeout: int = 30) -> str|None:
        """Solicitar motivo al usuario via termux-dialog."""
        pass
    
    @abstractmethod
    def solicitar_texto(self, pregunta: str, timeout: int = 30) -> str|None:
        """Solicitar texto al usuario (monto, persona, etc.)."""
        pass
```

**Implementación:**
- `TermuxDialogAdapter`: Usa `termux-dialog` con validación y timeouts

#### Puerto: `CloudAPIAdapter` (Sincronización nube)
```python
class CloudAPIAdapter(ABC):
    @abstractmethod
    def enviar_transaccion(self, payload: dict) -> dict:
        """Enviar transacción a la nube, retorna respuesta API."""
        pass
    
    @abstractmethod
    def verificar_estado_sincronizacion(self, event_id: str) -> bool:
        """Verificar si una transacción ya fue sincronizada."""
        pass
```

**Implementación:**
- `GoogleCloudFunctionAdapter`: POST a URL Cloud Function, manejo de reintentos y backoff

### 3.3 Adaptadores por Banco (Implementaciones Concretas)

Cada adaptador sigue la interfaz `BancoAdapter` pero transforma datos crudos de cada banco:

| Adaptador | Archivo | Descripción |
|-----------|---------|-------------|
| **`IBKAdapter`** | `adaptadores/ibk.py` | Notificaciones Interbank - transferencias de gasto |
| **`BBVAAdapter`** | `adaptadores/bbva.py` | Notificaciones BBVA - requiere solicitar tipo/monto/persona (prompt guiado) |
| **`YapeAdapter`** | `adaptadores/yape.py` | Notificaciones Yape - ingresos (formato estructurado, resguardo anti-duplicado fuerte) |
| **`PlinAdapter`** | `adaptadores/plin.py` | Notificaciones Plin - ingresos y gastos con lógica de consolidación en ventana |
| **`CompartamosAdapter`** | `adaptadores/compartamos.py` | Notificaciones Compartamos - solo ingresos, validación por monto y ventana corta |
| **`NFCAdapter`** | `adaptadores/nfc.py` | Pagos NFC / tarjeta física/unificada, consolidación con alertas bancarias previas |
| **`ManualAdapter`** | `adaptadores/manual.py` | Registro manual en Termux (efectivo, egresos sin notificación) |

**Interfaz común para todos los adaptadores (`puertos/banco_adapter.py`):**
```python
class BancoAdapter(ABC):
    @abstractmethod
    def es_mis_notificacion(self, datos_crudos: dict) -> bool:
        """¿Es esta notificación de mi banco? (basado en paquete o app name)"""
        pass
    
    @abstractmethod
    def normalizar_notificacion(self, datos_crudos: dict) -> dict:
        """Convertir datos crudos a diccionario normalizado.
        
        Campos obligatorios en resultado:
        - monto: float (siempre > 0)
        - tipo: "ingreso" o "gasto"
        - destinatario: str (persona/comercio/contraparte)
        - event_id: str (UUID único para identificación y deduplicación)
        - fecha_hora: str (formato ISO 8601)
        - canal: str (yope, plin, bbva, interbank, nfc, compartasco, manual)
        - motivo: str | null (pending - se solicitará al usuario)
        """
        pass
    
    @abstractmethod
    def necesita_motivo_obligatorio(self) -> bool:
        """Siempre retorna True para todos los bancos - el motivo es obligatorio."""
        pass
```

### 3.4 Módulos de Soporte y Configuración

#### `configurador.py` - Carga y Validación de Configuración Única
Responsable de:
- Leer archivo `config.yaml` (estructura completa vista en el plan)
- Cargar variables de entorno desde `.env` o sistema
- Validar campos requeridos y tipos de datos
- Proporcionar instancias de los puertos (Inyección de dependencias simple)

**Estructura de `config.yaml` (resumen):**
```yaml
bd:
  tipo: "sqlite"  # "postgresql" o "mysql" en futuro
  ruta_sqlite: "./local_gastos.db"

modo_operacion: "automate_broker"  # o "listener_directo"

ventana_consolidacion:
  minutos: 5  # Ventana para consolidar múltiples alertas

procesamiento:
  tiempo_espera_gps_segundos: 10
  tiempo_espera_dialogo_segundos: 30
  maximo_intentos_sincronizacion: 3

adaptadores_activos:
  - "ibk"
  - "bbva"
  - "yape"
  - "plin"
  - "compartamos"
  - "nfc"
  - "manual"

credenciales:
  google_cloud_func_url: "${GOOGLE_CLOUD_FUNC_URL}"
  google_sheets_id: "${GOOGLE_SHEETS_ID}"
  looker_studio_url: "${LOOKER_STUDIO_URL}"

logging:
  nivel: "INFO"
  archivo: "./logs/app.log"
```

**Carga de variables de entorno (.env):**
```
GOOGLE_CLOUD_FUNC_URL=https://us-centralis-xxx.cloudfunctions.net/gastos_api
GOOGLE_SHEETS_ID=1BxiMVs0XRA5nFMdKvBdBZjfbOatIs_cAnmM4BLlIgEY
LOOKER_STUDIO_URL=https://lookerstudio.google.com/reporting/xxx
```

#### `fifo_cola.py` - Gestión de Cola FIFO
- Detectar archivos nuevos en directorio configurado
- Procesar en orden de llegada
- Evitar procesamiento doble
- Ventana de consolidación de tiempo (configurable en config.yaml)

#### `consolidador.py` - Lógica de Evitación de Duplicados
- Buscar en SQLite si existe registro similar
- Criterios: mismo tipo + mismo monto ±10% dentro de ventana de tiempo
- Consolidar en lugar de crear nuevo registro
- Evitar preguntar motivo dos veces al usuario

#### `gps_handler.py` - Obtención de Ubicación
- Ejecutar `termux-location` con timeout definido (10s configurables)
- Si falla: buscar `last_known` en tabla de historial de SQLite
- Si no hay historial: marcar `gps_source = none`
- Retornar diccionario estandarizado con lat, lng, gps_source, mapa_url

#### `validador.py` - Validaciones de Negocio
- Validar que monto sea número > 0
- Validar tipo sea "ingreso" o "gasto"
- Sanitizar texto ingresado por usuario (termux-dialog)
- Detectar palabras clave de préstamos/abonos (para no preguntar unnecessarily)
- Formatear monto a PEN (Soles, $)

---

## 4. Modos de Operación Soportados

El sistema debe soportar DOS formas de captura, seleccionables desde `config.yaml`:

### Modo A: Automate File Broker (modo actual/primario)
**Flujo completo:**

1. **Automate (Android):** Recibe notificación push del banco
2. **Automate:** Escribe archivo de notificación al directorio configurado (`config.procesamiento.directorio_archivos`, ej. `/sdcard/Automate/notify/`)
3. **Service Broker (Termux):** Script o gestor Detecta archivo nuevo en directorio
4. **Termux/Python:** Ejecuta pipeline completo sobre el archivo:
   - Lee archivo → datos_crudos
   - **Dispatcher:** Enrutar a adaptador correspondiente (según `paquete` o `app name`)
   - **Adaptador:** Parsear y normalizar notificación (interfaz `BancoAdapter`)
   - **Validar duplicado:** `consolidador.verificar_duplicado_ventana()` - ¿hay registro similar en ventana 5 min?
   - **Si necesita motivo:** Solicitar via `termux-dialog` (obligatorio para todos los bancos)
   - **Obtener GPS:** `gps_handler.obtener_ubicacion()` - live/last_known/none fallback
   - **Insertar en SQLite:** Tabla `transacciones` con `status=consolidado, synced=0`, event_id único
   - **Sincronización:** Si hay internet: Enviar payload JSON a API Cloud (event_id único)
5. **API Cloud:** Recibe, valida esquema JSON, inserta/actualiza Google Sheets usando event_id para idempotencia
6. **Google Sheets:** Se actualiza → Looker Studio refleja cambios automáticamente

**Ventajas:**
- Ya está probado y funcionando en el proyecto actual
- Automate maneja la captura de notificaciones even cuando la app está cerrada
- File broker es más fácil de depurar e inspeccionar (revisar archivos en directorio)
- Compatible con el flujo FIFO existente y ventana de consolidación

**Desventajas:**
- Dependencia de que Automate escriba el archivo correctamente
- Un paso adicional en el flujo (automate → archivo → termux)

### Modo B: Listener Directo (modo alternativo/nuevo)
**Flujo simplificado:**

1. **Termux/Python (bucle while):** Ejecuta continuamente, cada X segundos (configurable, ej. 2s)
2. **Captura nativa:** Usa API nativa de Android para escuchar notificaciones push (librerías como `notifications2` o BroadcastReceiver en AndroidManifest)
3. **Procesamiento inmediato:** Cada notificación se procesa al momento sin archivos intermediarios
4. **Mismos pasos 4-6** del modo automate (validar, GPS, dialog, SQLite, API, Sheets)

**Implementación técnica:**
- Usar `notifications2` library para Python en Termux
- O configurar `BroadcastReceiver` nativo en AndroidManifest de la app Automate o una app auxiliar
- O polls checking for new notifications every N segundos

**Ventajas:**
- Flujo más directo, un paso menos (no necesita que Automate escriba archivos)
- Más en tiempo real (procesamiento al instante)
- No depende de la configuración de archivos de Automate

**Desventajas:**
- Requiere configuración adicional en Android (permissions, manifest, librerías)
- Mayor consumo de batería al estar siempre escuchando notificaciones
- Más complejo de depurar en dispositivo real
- Automate ya está instalado y configurado, no se necesita código extra en la app

### Configuración del Modo (ejemplo en `config.yaml`):
```yaml
modo_operacion: "automate_broker"  # "automate_broker" o "listener_directo"

automate_broker:
  directorio_archivos: "/sdcard/Automate/notify"
  monitoreo_polling_segundos: 5  # Cuanto tiempo espera Termux entre chequeos

listener_directo:
  activado: true
  tiempo_espera_bucle_segundos: 2  # Segundos entre cada iteración del bucle
  usar_notifications2_library: true  # ¿Usar librería external oReceiver nativo?
```

---

## 5. Arquitectura Hexagonal (Ports and Adapters) en Profundidad

### 5.1 Principio Central
La lógica de negocio está en el **centro** (sin dependencias externas), rodeada de **puertos** (interfaces/contratos) y **adaptadores** (implementaciones concretas). This permite cambiar cualquiera de los adaptadores sin tocar la lógica central.

### 5.2 Capas desde el Centro hacia afuera

```
+=================================================================+
|                CAPA CENTRO: DOMINIO (PURE)                      |
+=================================================================+
|  Entidades: Transaccion, NotificacionCruda, AbonoPrestamo       |
|  Casos de uso: RegistrarMovimiento, SincronizarNube,           |
|  ValidarDuplicado, CapturarUbicacion                          |
|  ← NINGUNA dependencia externa (no importa termux, sqlite, API)|
+-----------------------|-----------------------------------+
|                       PUERTOS (Interfaces)                    |
|  NotificacionListener, DatabaseAdapter, GPSProvider,          |
|  DialogProvider, CloudAPIAdapter - definen "qué" hacer,     |
|  pero no "cómo"                                               |
+-----------------------|-----------------------------------+
|                      ADAPTADORES (Implementaciones)           |
|  SQLiteAdapter, PostgreSQLAdapter, GPSTermuxLive,             |
|  TermuxDialogAdapter, GoogleCloudFunctionAdapter,             |
|  IBKAdapter, BBVAAdapter, YapeAdapter, ...                    |
|  ← Implementan los puertos usando detalles técnicos           |
+=================================================================+
```

### 5.3 Flujo de Datos a través de la Arquitectura Hexagonal

```
Entrada: Notificación cruda del banco
         ↓
    [Puerto: NotificacionListener]
    (¿Modo broker? ¿Modo listener?)  ← Selección en runtime desde config
     ↓
    [Lógica de Dominio: Casos de uso]
    (validar, consolidar, asignar motivo si es necesario)
     ↓
    [Puerto: DatabaseAdapter] ←→ [SQLite o PostgreSQL según config.bd.tipo]
    ↓
    [Puerto: GPSProvider] → obtener ubicación (live/last_known/none)
    ↓
    [Puerto: DialogProvider] → solicitar motivo al usuario (siempre obligatorio)
    ↓
    [Puerto: CloudAPIAdapter] → enviar payload a Google Cloud Function
    ↓
    Salida: Datos en SQLite + sincronización a Google Sheets
```

### 5.4 Beneficios de esta Estructura

1. **Cambiar de SQLite a PostgreSQL:**
   - Solo crear `PostgreSQLAdapter` implementando `DatabaseAdapter`
   - Cambiar `config.bd.tipo: "postgresql"` en config.yaml
   - **Código central sin modificar**

2. **Soportar ambos modos operación:**
   - Diferentes implementaciones del mismo puerto `NotificacionListener`
   - `EstrategiaAutomateBroker` vs `EstrategiaListenerDirecto`
   - Selección en tiempo de ejecución desde `config.modos_operacion`

3. **Testing fácil:**
   - Falsificaciones (mocks) de cualquiera de los puertos
   - Testing de lógica de dominio sin necesidad de SQLite real
   - Testing de adaptadores con datos de prueba controlados

4. **Agregar nuevo banco:**
   - Crear nuevo archivo `adaptadores/nuevo_banco.py`
   - Implementar `BancoAdapter` interface
   - Agregar nombre a `config.adaptadores_activos`
   - **Ningún archivo existente modificado**

5. **Cambiar credenciales de API:**
   - Modificar variables de entorno `.env`
   - No tocar código fuente
   - Reiniciar aplicación

### 5.5 Inyección de Dependencias (Simplificada)

En `main.py` o punto de entrada:

```python
from configurador import Configurador
from puertos import DatabaseAdapter, NotificacionListener, GPSProvider, DialogProvider, CloudAPIAdapter

def main():
    # 1. Cargar configuración
    config = Configurador.cargar_desde_archivo("config.yaml")
    
    # 2. Crear instancias de adaptadores según config
    db: DatabaseAdapter
    if config.bd.tipo == "sqlite":
        db = SQLiteAdapter(ruta=config.bd.ruta_sqlite)
    # elif config.bd.tipo == "postgresql": ...
    
    listener: NotificacionListener
    if config.modos_operacion == "automate_broker":
        listener = EstrategiaAutomateBroker(directorio=config.automate_broker.directorio_archivos)
    else:
        listener = EstrategiaListenerDirecto()
    
    gps: GPSProvider = GPSTermuxLive(timeout=config.procesamiento.tiempo_espera_gps_segundos)
    dialog: DialogProvider = TermuxDialogAdapter(timeout=config.procesamiento.tiempo_espera_dialogo_segundos)
    cloud: CloudAPIAdapter = GoogleCloudFunctionAdapter(url=config.credenciales.google_cloud_func_url)
    
    # 3. Ejecutar según modo
    if config.modos_operacion == "automate_broker":
        ejecutar_modo_broker(config, db, listener, gps, dialog, cloud)
    else:
        ejecutar_modo_listener_directo(config, db, listener, gps, dialog, cloud)

if __name__ == "__main__":
    main()
```

---

## 6. Patrones de Diseño Documentados

### 6.1 Arquitectura Hexagonal (Ports and Adapters)
**Principio:** Isolación total de la lógica de negocio de los detalles de implementación.

**En este proyecto:**
- **Centro:** Lógica pura (entidades, casos de uso) - `dominio/`
- **Puertos:** Interfaces de contrato - `puertos/`
- **Adaptadores:** Implementaciones técnicas - `adaptadores/`, `infraestructura/`

**Flujo:** Centro ←→ Puertos ←→ Adaptadores

**Beneficios aplicados a este proyecto:**
- Cambiar BD: Un solo archivo nuevo, el resto intacto
- Agregar banco: Un solo archivo nuevo, el resto intacto
- Cambiar modo operación: Misma llamada, distinta implementación de puerto
- Testing: Mocks de puertos, sin dependencias externas obligatorias

### 6.2 Patrón Strategy (Modo Operación)
**Problem:** Soportar dos modos totalmente diferentes de captura de notificaciones, cambiable sin code changes.

**Solution:** Cada modo es una estrategia que implementa la misma interfaz.

**Aplicado:** `EstrategiaAutomateBroker` vs `EstrategiaListenerDirecto`  
Ambas implementan `ModoOperacionStrategy` con métodos `procesar_notificacion()` y `esta_activo()`.

**Uso:** `fabrica_estrategias.crear(config.modos_operacion)` devuelve la estrategia correcta.

### 6.3 Patrón FIFO Queue
**Contexto:** Notificaciones pueden llegar desordenadas; múltiples alertas disparan un mismo gasto.

**Solution:** Procesar en orden de llegada, con ventana de consolidación.

**Aplicado:** Cola FIFO en Termux, ventana de 5 minutos configurables.  
Si llega notificación dentro de la ventana → consolidar, no repetir motivo.  
Si pasa el tiempo → nuevo registro, nueva pregunta de motivo.

### 6.4 Patrón Offline-First
**Principio:** La aplicación funciona completamente sin internet.

**Aplicado:** Todos los movimientos se guardan primero en SQLite con `synced=0`.  
Sincronización a la nube solo cuando hay conexión. Si falla, reintentar luego.  
Modo offline completo funcional: ver historial, buscar, categorías, KPIs básicos.

### 6.5 Patrón Adapter (por banco) - Ja Implementado
**Contexto:** Cada banco tiene formato de notificación diferente.

**Aplicado:** 7 adaptadores distintos (IBK, BBVA, Yape, Plin, Compartamos, NFC, Manual).  
Todos implementan la misma interfaz `BancoAdapter`.  
Fácil agregar nuevos: crear nuevo archivo, agregar a config.

### 6.6 Patrón Configuration (Archivo Único)
**Problem:** Muchas variables configurables: BD, modo, timeouts, bancos, credenciales.

**Solution:** Un solo archivo `config.yaml` con todas las secciones + variables de entorno `.env` para secretos.

**Aplicado:** Estructura completa vista en el plan.  
Beneficio: "Configuration as Code", versionado junto con el código, fácil rollback.

---

## 7. Flujo de Datos Detallado

### Flujo Modo A (Automate Broker) - Completo Paso a Paso

```
PASO 1: Automate captura notificación
-------------------------------------
Automate (Android) recibe push del banco (Yape, Plin, BBVA, Interbank, NFC, Compartamos)
↓
Automate procesa y deja archivo formateado en:
  /sdcard/Automate/notify/ (directorio configurado en config.yaml)
↓
Nombre de archivo: contiene timestamp y datos identificadores

PASO 2: Termux detecta y comienza procesamiento
-----------------------------------------------
Termux (ejecutándose en bucle o triggered por nuevo archivo)
  ↓
Lee archivo nuevo → datos_crudos = {
    "paquete": "pe.com.interbank.mobilebanking",
    "app": "Interbank", 
    "titulo": "Confirmacion Plin",
    "cuerpo": "Plineaste S/ 200.00 a Carlos Perez",
    "fecha_hora": "1795272840.52",
    "monto": "200.00" (si viene en el cuerpo)
}

PASO 3: Enrutamiento y adaptador
---------------------------------
Config.adaptadores_activos contiene "ibk"
↓
Dispatcher verifica: IBKAdapter.es_mis_notificacion(datos_crudos) → True (paquete coincide)
↓
IBKAdapter.normalizar_notificacion(datos_crudos) → diccionario normalizado:
{
    "monto": 200.00,
    "tipo": "gasto",
    "destinatario": "Carlos Perez",
    "event_id": "c9b8e7a5-fd3f-4a1c-bd1a-7f2e3d6b9a1c",  # UUID generado
    "canal": "interbank",
    "fecha_hora_iso": "2026-11-21T09:54:00-05:00",
    "motivo": null  # Pendiente - se solicitará después
}

PASO 4: Validación de duplicado en ventana
-------------------------------------------
Consolidador.verificar_duplicado_ventana(normalizado) → consulta SQLite
- ¿Hay registro en los últimos 5 min (config.ventana_consolidacion.minutos) 
-  con mismo tipo (gasto) + mismo monto (±10%)?
→ False (no hay reciente) → Siguiente paso

PASO 5: Solicitud de motivo (OBLIGATORIO para todos los bancos)
---------------------------------------------------------------
Dialogo termux-dialog aparece:
"¿Cuál fue el motivo de este gasto?"
Usuario ingresa: "Prestamo urgente" (o "Compra supermercado", etc.)
↓
El motivo se añade al diccionario normalizado:
"motivo": "Prestamo urgente"

PASO 6: Obtención de GPS con fallback
----------------------------------------
GPSTermuxLive.obtener_ubicacion() ejecuta:
 1. termux-location (timeout 10s configurables)
 2. ¿Resultado válido? → Si → {lat: -11.994210, lng: -77.062840, gps_source: "live"}
 3. No → Consultar SQLite por última ubicación válida (GPSCacheSQLite)
 4. ¿Existe? → Si → {lat: última, lng: última, gps_source: "last_known"}
 5. No → {lat: None, lng: None, gps_source: "none"} - El movimiento SÍ se guarda

Resultado GPS añadido al normalizado:
"latitud": -11.994210, "longitud": -77.062840, "fuente_gps": "live", "mapa": "https://maps.google.com/..."

PASO 7: Insertar en SQLite (Tabla transacciones)
--------------------------------------------------
SQLiteAdapter.guardar_transaccion(diccionario completo con ~40 campos):

Campos clave insertados:
- id_transaccion: "c9b8e7a5-fd3f-4a1c-bd1a-7f2e3d6b9a1c"
- fecha_hora_epoch: 1795272840.52
- fecha: "2026-11-21"
- hora: "09:54:00"
- trimestre: "2026-Q4"
- app: "Interbank"
- paquete: "pe.com.interbank.mobilebanking"
- dispositivo: "Celular-Erick"
- tipo: "Gasto"
- medio: "Transferencia"
- monto_total: 200.00
- moneda: "PEN"
- destinatario: "Carlos Perez"
- motivo: "Prestamo urgente"
- categoria: "Prestamos"
- es_prestamo: 1
- monto_pagado: 0.00
- saldo_pendiente: 200.00
- estado_prestamo: "activo"
- looker: 1
- latitud: -11.994210, longitud: -77.062840
- fuente_gps: "live"
- mensaje_raw: "[Plin] Plineaste S/ 200.00 a Carlos Perez"
- status: "consolidado"
- sincronizado: 0  ← Pendiente de sincronización a la nube
- intentos_sync: 0
- ultimo_error_sync: ""

PASO 8: Sincronización a Nube (si hay internet)
------------------------------------------------
Si en línea:
  1. Construir payload JSON para API Cloud:
   {
     "event_id": "c9b8e7a5-fd3f-4a1c-bd1a-7f2e3d6b9a1c",
     "app": "Interbank",
     "tipo": "gasto",
     "monto": 200.00,
     "moneda": "PEN",
     "motivo": "Prestamo urgente",
     "destinatario": "Carlos Perez",
     "latitud": -11.994210,
     "longitud": -77.062840,
     "gps_source": "live",
     "mensaje_raw": "[Plin] Plineaste S/ 200.00 a Carlos Perez",
     "fecha_iso": "2026-11-21T09:54:00-05:00"
   }
   ↓
  2. API Cloud receives payload ✓
  3. Valida esquema JSON ✓
  4. Inserta/Actualiza en Google Sheets usando event_id (idempotente) ✓
  5. Respuesta 2xx confirmada ✓
  6. SQLiteAdapter.actualizar_sincronizacion("c9b8e7a5-...", "1")
  ↓
  ✅ Sincronización exitosa - ahora el registro es "mirror" en la nube

Si NO hay internet:
  ↓
  Mantener sincronizado: 0 en SQLite
  ↓
  ✅ Movimiento guardado localmente, se sincronizará próximo ciclo cuando haya red
  ↑
  El usuario puede continuar usando la app offline completamente
```

### Flujo Modo B (Listener Directo) - Simplificado

Igual pasos 3-8, pero el paso 1-2 es diferente:
```
PASO 1: Listener directo captura nativa
----------------------------------------
Termux bucle while (cada 2s configurables) detecta notificación push nativa
de Android (usando notifications2 library o Receiver configurado)
↓
Datos crudos similares, pero sin archivo intermediario

PASO 2-8: Mismo flujo que modo broker
a partir del enrutamiento al adaptador
```

---

## 8. Estructura de Directorios del Proyecto

Tras aplicar la arquitectura, la organización física del proyecto sería:

```
/home/giancarlo/local-gestion-gastos/
├── ARCHITECTURE.md          # Este archivo (visión general + patrones)
├── Agents.md                # Guía de agentes y buenas prácticas (ya creado)
├── config.yaml              # Configuración única (se creará después)
├── .env                     # Variables de entorno (secreciones, no versionar)
├── main.py                  # Punto de entrada - usa estrategias y inyección de dependencias
│
├── dominio/                 # Lógica de negocio pura (sin dependencias externas)
│   ├── entidades.py         # Transaccion, NotificacionCruda, AbonoPrestamo
│   └── casos_uso/           # RegistrarMovimiento, SincronizarNube, etc.
│
├── puertos/                 # Interfaces/contratos (lo que el dominio usa)
│   ├── notificacion_listener.py  # NotificacionListener ABC
│   ├── database_adapter.py     # DatabaseAdapter ABC
│   ├── gps_provider.py       # GPSProvider ABC
│   ├── dialog_provider.py    # DialogProvider ABC
│   └── cloud_api_adapter.py  # CloudAPIAdapter ABC
│   └── banco_adapter.py      # BancoAdapter ABC + campos normalizados
│
├── adaptadores/             # Implementaciones concretas
│   ├── ibk.py               # IBKAdapter -> BancoAdapter
│   ├── bbva.py              # BBVAAdapter -> BancoAdapter
│   ├── yape.py              # YapeAdapter -> BancoAdapter
│   ├── plin.py              # PlinAdapter -> BancoAdapter
│   ├── compartamos.py       # CompartamosAdapter -> BancoAdapter
│   ├── nfc.py               # NFCAdapter -> BancoAdapter
│   └── manual.py            # ManualAdapter -> BancoAdapter
│
│   └── infraestructura/     # Adaptadores de soporte
│       ├── sqlite_adapter.py       # DatabaseAdapter -> SQLite
│       ├── postgres_adapter.py     # DatabaseAdapter -> PostgreSQL (futuro)
│       ├── gps_termpux_live.py   # GPSProvider -> termux-location
│       ├── gps_cache_sqlite.py   # GPSProvider -> última de SQLite
│       ├── termux_dialog_adapter.py  # DialogProvider -> termux-dialog
│       └── google_cloud_adapter.py  # CloudAPIAdapter -> Cloud Function
│
├── modulios/                # Módulos de soporte
│   ├── fifo_cola.py         # Gestión cola FIFO, detección archivos nuevos
│   ├── consolidador.py      # Lógica ventana consolidación, deduplicado
│   ├── validador.py         # Validaciones de negocio (montos, tipos, sanitized)
│   └── gps_handler.py       # Wrapper para obtener/fallback GPS
│
├── logs/                    # Logs de aplicación (rotación configurables)
├── scripts/                 # Scripts de ayuda, backup, migración
├── .gitignore
├── README.md                # Documentación funcional (ya existe, vista earlier)
└── opencode.json            # Configuración OpenCode
```

---

## 9. Migración y Evolución Futura

### 9.1 Cambiar de SQLite a PostgreSQL
**Qué cambiar:**
1. En `config.yaml`: `bd.tipo: "postgresql"`
2. Crear `infraestructura/postgres_adapter.py` implementando `DatabaseAdapter`
3. Asegurar operaciones SQL con parámetros (no hardcodeado)
4. Probar con esquema idéntico en PostgreSQL

**Qué NO cambiar:**
- Lógica de dominio (casos de uso en `dominio/`)
- Adaptadores de banco (IBKAdapter, etc. - unchanged)
- Archivo config.yaml (solo cambia un campo `tipo`)
- Código que llama a los puertos (usando abstracciones)

### 9.2 Agregar Nuevo Banco (ej. Nubank)
**Qué cambiar:**
1. Crear `adaptadores/nubank.py` con clase `NubankAdapter(BancoAdapter)`
2. Agregar "nubank" a `config.adaptadores_activos`
3. Implementar `es_mis_notificacion()` y `normalizar_notificacion()` para formato Nubank

**Qué NO cambiar:**
- Ningún archivo existente de otros adaptadores
- Lógica central, casos de uso
- Estructura de SQLite o schema

### 9.3 Agregar Nuevo Modo de Operación
**Qué cambiar:**
1. Crear nueva clase `NuevoModoStrategy(ModoOperacionStrategy)`
2. Implementar lógica específica para nuevo modo
3. Agregar condición en `fabrica_estrategias.crear()`
4. Actualizar `config.yaml` con nuevo modo y parámetros

**Qué NO cambiar:**
- Lógica de dominio central
- Puertos (interfaces unchanged)
- Adaptadores de banco
- Estructura de SQLite

### 9.4 Cambiar Credenciales de API
**Qué cambiar:**
- Modificar variables de entorno `.env`
- No tocar código fuente

**Qué NO cambiar:** Cualquier archivo de código, estructura de BD, lógica de negocio

---

## 10. Checklist de Validación

El archivo ARCHITECTURE.md fue validado considerando:

- ✅ Toda la documentación existente revisada (C1-C2-Diagrama-BD + todos los C3-adaptadores + README.md functional)
- ✅ Requisitos del usuario: dos modos operación, configuración única, adaptadores separados, arquitectura flexible
- ✅ Buenas prácticas: Arquitectura Hexagonal, Inversión de Dependencias, Configuración Centralizada
- ✅ Patrones identificados y documentados: FIFO, Offline-First, Adapter, Strategy, Configuration
- ✅ Idioma: Todo en español, documentación y comentarios en código
- ✅ Escalabilidad: Fácil cambiar BD, agregar bancos nuevos, cambiar modo operación
- ✅ Testing: Mocks posibles de puertos, testing sin dependencias externas obligatorias
- ✅ ✅ Compatibilidad con proyecto existente (mismos datos SQLite, mismos adaptadores vistos en docs)

---

## 11. Próximos Pasos

1. **Revisar y validar este ARCHITECTURE.md** con el usuario - ¿está acordé con lo esperado?
2. **Crear el archivo `config.yaml`** con estructura propuesta
3. **Crear el archivo `.env`** template (variables de entorno)
4. **Migrar lógica actual** a la nueva arquitectura modular (poco a poco, adaptador por adaptador)
5. **Probar cada adaptador** con datos reales de cada banco (Yape, Plin, BBVA, Interbank, NFC, Compartamos, Manual)
6. **Probar ambos modos** (broker automate y listener directo) con mismas notificaciones
7. **Hacer commit incremental** - un adaptador por commit, más fácil review y debug
8. **Probar cambio de configuración** (BD tipo, modo operación) sin código changes
9. **Usar el archivo como referencia** para desarrollo futuro y nuevos contribuyentes (aunque sea solo el autor)

---

## 10. Checklist de Validación

El archivo ARCHITECTURE.md fue validado considerando:

- ✅ Toda la documentación existente revisada (C1-C2-Diagrama-BD + todos los C3-adaptadores + README.md functional)
- ✅ Requisitos del usuario: dos modos operación, configuración única, adaptadores separados, arquitectura flexible
- ✅ Buenas prácticas: Arquitectura Hexagonal, Inversión de Dependencias, Configuración Centralizada
- ✅ Patrones identificados y documentados: FIFO, Offline-First, Adapter, Strategy, Configuration
- ✅ Idioma: Todo en español, documentación y comentarios en código
- ✅ Escalabilidad: Fácil cambiar BD, agregar bancos nuevos, cambiar modo operación
- ✅ Testing: Mocks posibles de puertos, testing sin dependencias externas obligatorias
- ✅ ✅ Compatibilidad con proyecto existente (mismos datos SQLite, mismos adaptadores vistos en docs)

---

## 12. Interfaz de Línea de Comandos (CLI) y Acciones Manuales

### 12.1 Propósito
Este sección documenta el punto de entrada manual para operaciones que requieren intervención directa del usuario, bypassing los flujos automatizados (Automate/File broker). La CLI permite:
- Abrir y consultar la base de datos SQLite
- Ejecutar comandos SQL personalizados
- Sincronizar datos manualmente con la nube
- Registrar gastos/ingresos manuales completos
- Diagnósticos y mantenimiento del sistema

### 12.2 Punto de Entrada: `cli.py`
El archivo `main.py` incluye un modo CLI activable mediante bandera `--manual` o `-m`:

```bash
# Ejemplos de uso:
python main.py --manual list                                     # Listar todas las transacciones
python main.py --manual show --id c9b8e7a5-fd3f-4a1c-bd1a-7f2e3d6b9a1c  # Mostrar transacción específica
python main.py --manual sync                                     # Forzar sincronización a la nube
python main.py --manual insert --motivo "Pago de servicio" --monto 50.00 --tipo gasto  # Insertar manualmente
python main.py --manual db --cmd "SELECT * FROM transacciones WHERE sincronizado = 0"  # Consultar SQL personalizado
```

### 12.3 Módulo de Registro Manual de Gastos/Ingresos

Dentro de la arquitectura hexagonal, se añade un nuevo caso de uso:

#### Caso de Uso: `RegistrarManual`
**Entrada:** Diccionario con datos del movimiento (o parámetros CLI)
**Salida:** Transacción insertada en SQLite con `status = consolidado, synced = 0`

**Flujo:**
1. El módulo solicita los datos obligatorios si no fueron provistos por CLI:
   - Tipo: `ingreso` o `gasto` (validado)
   - Monto: número > 0 (validado)
   - Destinatario/Persona: nombre del comercio o persona involucrada
   - Motivo: descripción del movimiento (obligatorio, sin excepción)
   - Medio: `Cuenta`, `Tarjeta`, `NFC`, `Efectivo`, `Transferencia`, etc.
   - Categoría: opcional (ej. `Comestibles`, `Prestamos`, `Salarios`, etc.)
   - Ubicación GPS: opcional (si se quiere capturar en ese momento)

2. **Obtención de GPS (opcional):**
   - Si el usuario quiere GPS, se ejecuta `gps_handler.obtener_ubicacion()` con timeout
   - Si no, se marca `gps_source = none` y `latitud/lng = None`

3. **Generación de event_id:**
   - Se genera un UUID único para la transacción

4. **Validación de duplicado:**
   - Se consulta la ventana de consolidación (configurable, default 5 min)
   - Si existe registro similar → consolidar en lugar de crear nuevo
   - Si no, prosigue con el insert

5. **Insert en SQLite:**
   - Se inserta en tabla `transacciones` con todos los campos
   - `sincronizado: 0` (pendiente de sync a nube)
   - `status: consolidado`
   - `intentos_sync: 0`

6. **Confirmación:**
   - Se muestra resumen de lo insertado
   - Opción de sincronizar inmediatamente a la nube

#### Ejemplo conceptual en Python (CLI):

```python
# Dentro de main.py modo manual
if args.manual == "insert":
    motivo = input("Motivo del movimiento: ") if not args.motivo else args.motivo
    monto = float(input("Monto: ")) if not args.monto else args.monto
    tipo = input("Tipo (ingreso/gasto): ") if not args.tipo else args.tipo
    destinatario = input("Persona o comercio: ") if not args.destinatario else args.destinatario
    medio = input("Medio (Cuenta/Tarjeta/NFC/Efectivo/Transferencia): ") if not args.medio else args.medio
    
    # Capturar GPS opcional
    gps = gps_handler.obtener_ubicacion() if args.gps else None
    
    # Registrar manual
    event_id = db.guardar_transaccion({
        "id_transaccion": str(uuid.uuid4()),
        "fecha_hora_epoch": time.time(),
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M:%S"),
        "trimestre": f"{datetime.now().year}-Q{((datetime.now().month - 1) // 3) + 1}",
        "app": "manual",
        "paquete": "manual.entry",
        "dispositivo": "CLI-Manual",
        "tipo": tipo,
        "medio": medio,
        "monto_total": monto,
        "moneda": "PEN",
        "destinatario": destinatario,
        "motivo": motivo,
        "categoria": "Manual",
        "es_prestamo": 0,
        "monto_pagado": 0.00,
        "saldo_pendiente": monto if tipo == "gasto" else 0.00,
        "estado_prestamo": "n/a",
        "looker": 0,
        "latitud": gps["lat"] if gps else None,
        "longitud": gps["lng"] if gps else None,
        "fuente_gps": gps["gps_source"] if gps else "none",
        "mensaje_raw": f"Entrada manual: {motivo} - S/ {monto}",
        "status": "consolidado",
        "sincronizado": 0,
        "intentos_sync": 0,
        "ultimo_error_sync": ""
    })
    
    print(f"\n✅ Transacción registrada manualmente!")
    print(f"   event_id: {event_id}")
    print(f"   Motivo: {motivo}")
    print(f"   Monto: S/ {monto}")
    print(f"   Sincronizado: NO (0) - Ejecute 'python main.py --manual sync' para enviar a la nube")
```

### 12.4 Comandos SQL y Operaciones de Base de Datos

El módulo de CLI incluye acceso directo a la base de datos para operaciones de diagnóstico, mantenimiento y consulta personalizada.

#### 12.4.1 Acceso a SQLite
El CLI usa la misma `SQLiteAdapter` que el flujo automático, asegurando consistencia en el esquema.

**Estructura de tablas (según Diagrama-BD.uml):**

```sql
-- Tabla: transacciones (vista rápida)
CREATE TABLE transacciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_transaccion TEXT UNIQUE,        -- UUID identificador único
    fecha_hora_epoch REAL,             -- Marca de tiempo epoch
    fecha_iso TEXT,                    -- Formato ISO 8601
    fecha TEXT,                        -- Fecha YYYY-MM-DD
    hora TEXT,                         -- Formato HH:MM:SS
    trimestre TEXT,                    -- Ej: 2026-Q4
    app TEXT,                          -- Aplicación origen
    paquete TEXT,                      -- Paquete Android
    dispositivo TEXT,                  -- Nombre del dispositivo
    tipo TEXT,                         -- "Ingreso" o "Gasto"
    medio TEXT,                        -- "Cuenta", "Tarjeta", "NFC", etc.
    monto_total REAL,                  -- Monto en PEN
    moneda TEXT,                       -- "PEN"
    destinatario TEXT,                 -- Persona o comercio
    motivo TEXT,                       -- Descripción del movimiento
    categoria TEXT,                    -- Clasificación (Prestamos, Comestibles, etc.)
    es_prestamo INTEGER,               -- 1 = sí, 0 = no
    monto_pagado REAL,                 -- Para préstamos: cuotas pagadas
    saldo_pendiente REAL,              -- Saldo restante por pagar
    estado_prestamo TEXT,              -- "activo", "parcial", "saldado"
    looker INTEGER,                    -- Indicador para Looker Studio
    latitud REAL,                      -- Coordenada geográfica
    longitud REAL,                     -- Coordenada geográfica
    fuente_gps TEXT,                   -- "live", "last_known", "none"
    mapa TEXT,                         -- URL de Google Maps
    mensaje_raw TEXT,                  -- Mensaje original del banco
    status TEXT,                       -- "consolidado", "pendiente"
    sincronizado INTEGER,              -- 0 = no sincronizado, 1 = sincronizado
    intentos_sync INTEGER,              -- Contador de reintentos
    ultimo_error_sync TEXT             -- Último error en texto
);

-- Tabla: notificaciones_crudas
CREATE TABLE notificaciones_crudas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recibido_en REAL,
    paquete TEXT,
    app TEXT,
    dispositivo TEXT,
    titulo TEXT,
    cuerpo TEXT,
    id_transaccion_vinculada TEXT,     -- FK opcional a transacciones
    resultado_proceso TEXT             -- "consolidada", "duplicado", "ignorada"
);

-- Tabla: abonos_prestamo
CREATE TABLE abonos_prestamo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_transaccion_prestamo TEXT,      -- FK a la transacción de la deuda
    id_transaccion_ingreso TEXT,       -- FK al abono/ingreso que paga la deuda
    fecha_abono TEXT,                  -- Fecha del abono
    monto_abono REAL,                  -- Monto pagado
    saldo_restante REAL,               -- Saldo después del abono
    nota TEXT                          -- Observaciones
);
```

#### 12.4.2 Comandos SQL Ejemplos a través CLI

```bash
# Listar todas las transacciones pendientes de sincronizar
python main.py --manual db --cmd "SELECT id_transaccion, fecha, motivo, monto_total, destinatario FROM transacciones WHERE sincronizado = 0 ORDER BY fecha_hora_epoch DESC LIMIT 10;"

# Ver resumen de gastos por categoría
python main.py --manual db --cmd "SELECT categoria, SUM(monto_total) as total, COUNT(*) as cantidad FROM transacciones WHERE tipo = 'Gasto' AND sincronizado = 1 GROUP BY categoria ORDER BY total DESC;"

# Ver historial de un préstamo en específico
python main.py --manual db --cmd "SELECT fecha_iso, monto_pagado, saldo_pendiente, estado_prestamo FROM transacciones WHERE es_prestamo = 1 AND destinatario = 'Carlos Perez' ORDER BY fecha_hora_epoch DESC;"

# Ver últimas 5 notificaciones crudas sin procesar
python main.py --manual db --cmd "SELECT id, titulo, cuerpo, resultado_proceso, recibido_en FROM notificaciones_crudas ORDER BY recibido_en DESC LIMIT 5;"

# Contar total de transacciones por estado de sincronización
python main.py --manual db --cmd "SELECT sincronizado, COUNT(*) as total FROM transacciones GROUP BY sincronizado;"

# Buscar transacciones sin GPS
python main.py --manual db --cmd "SELECT id_transaccion, fecha, motivo, latitud, longitud FROM transacciones WHERE latitud IS NULL OR longitud IS NULL;"

# Actualizar sincronización manualmente (ej. después de fallo de red)
python main.py --manual db --cmd "UPDATE transacciones SET sincronizado = 1, ultimo_error_sync = '' WHERE event_id = 'c9b8e7a5-fd3f-4a1c-bd1a-7f2e3d6b9a1c';"
```

#### 12.5 Flujo de Sincronización Manual

#### Flujo "Sync Now" (Sincronizar Ahora)

```
1. Usuario ejecuta: python main.py --manual sync
2. CLI carga configuración y crea instancia de GoogleCloudFunctionAdapter
3. CLI consulta SQLite por transacciones con sincronizado = 0
4. Para cada transacción pendiente:
   a. Construir payload JSON (mismo formato que el flujo automático)
   b. POST a Google Cloud Function URL (config.credenciales.google_cloud_func_url)
   c. Verificar respuesta:
      - Si 2xx: Actualizar sincronizado = 1 en SQLite, imprimir ✅
      - Si error: Incrementar intentos_sync, imprimir ⚠️ con código de error
5. Mostrar resumen: "X de Y transacciones sincronizadas exitosamente"
```

### 12.6 Estructura de Directorios Actualizada

Se añade un nuevo directorio opcional para scripts manuales:

```
/home/giancarlo/local-gestion-gastos/
├── ... (estructura existente)
├── cli.py                      # Punto de entrada CLI (nuevo)
├── manual/                     # Módulo de registro manual (nuevo)
│   ├── __init__.py
│   ├── registrar.py            # Lógica de registro manual
│   └── sync.py                 # Lógica de sincronización manual
├── scripts/                    # Scripts de ayuda, backup, migración
│   ├── backup_db.py            # Backup de SQLite
│   └── diagnostico.py          # Diagnóstico del sistema
├── main.py                     # Punto de entrada principal (actualizado con flags --manual)
└── ...
```

### 12.7 Beneficios de la Interfaz Manual

1. **Mantenimiento:** Permite limpiar, corregir o modificar registros directamente en SQLite sin necesidad de reprocesar notificaciones
2. **Emergencias:** Si el flujo automático falla o hay datos perdidos, el usuario puede ingresar manualmente las transacciones perdidas
3. **Flexibilidad:** Casos de uso que no caben en los flujos automatizados (ej. transferencias entre cuentas personales, ingresos en efectivo sin notificación)
4. **Diagnóstico:** Consultas SQL directas para entender el estado actual de los datos
5. **Testing:** Forma de probar la inserción y el esquema de la base de datos sin depender de las notificaciones bancarias

### 12.8 Consideraciones de Seguridad

- El CLI debe ser ejecutado en el mismo entorno (Termux en Android) donde opera el sistema
- No se deben versionar credenciales en el código; usar siempre variables de entorno `.env`
- Los comandos SQL tienen acceso completo a la base de datos; usar con cuidado
- El comando `sync` solo enviará transacciones con `sincronizado = 0`, manteniendo la idempotencia por `event_id`

---

## 11. Próximos Pasos

1. **Revisar y validar este ARCHITECTURE.md** con el usuario - ¿está acordé con lo esperado?
2. **Crear el archivo `config.yaml`** con estructura propuesta
3. **Crear el archivo `.env`** template (variables de entorno)
4. **Migrar lógica actual** a la nueva arquitectura modular (poco a poco, adaptador por adaptador)
5. **Probar cada adaptador** con datos reales de cada banco (Yape, Plin, BBVA, Interbank, NFC, Compartamos, Manual)
6. **Probar ambos modos** (broker automate y listener directo) con mismas notificaciones
7. **Hacer commit incremental** - un adaptador por commit, más fácil review y debug
8. **Probar cambio de configuración** (BD tipo, modo operación) sin código changes
9. **Usar el archivo como referencia** para desarrollo futuro y nuevos contribuyentes (aunque sea solo el autor)
10. **Implementar el módulo CLI** y de registro manual según especificación en la Sección 12

---

## 13. Formato de Notificaciones y Inputs

Esta sección documenta el formato de los datos de notificación que el sistema captura, tanto desde el entorno Termux como desde JSON de Automate. Este información es crítica para los adaptadores (`BancoAdapter`) que deben parsear estos datos crudos y convertirlos a un diccionario normalizado.

### 13.1 Contexto
Las notificaciones bancarias llegan al sistema a través de dos caminos principales:
1. **Modo Automate File Broker:** Automate escribe un archivo JSON con los datos de la notificación
2. **Modo Listener Directo:** Termux captura notificaciones nativas del sistema Android

Ambos formatos contienen información superpuesta pero con estructuras levemente diferentes, y los adaptadores deben ser capaces de extraer los campos esenciales de cualquiera de ellos.

### 13.2 Formato de Notificación Termux (Output nativo)

Cuando Termux captura una notificación a través de sus mecanismos nativos (ej. usando `termux-notification-listener` o bucle de polling), el output tiene esta estructura:

```json
{
  "id": 28702580,                              // ID único de la notificación
  "tag": "",                                   // Tag/category opcional
  "key": "0|com.bcp.innovacxion.yapeapp|28702580|null|10424",  // Clave única formato "paquete|id"
  "group": "",                                 // Grupo de notificación
  "packageName": "com.bcp.innovacxion.yapeapp", // Nombre paquete Android
  "title": "Confirmación de Pago",             // Título de la notificación
  "content": "Yape! ERICK RAMOS te envió un pago por S/ 1", // Cuerpo/mensaje principal
  "when": "2026-11-22 00:23:52"                // Marca de tiempo
}
```

**Campos esenciales para parseo:**
- `packageName`: Identifica qué banco/billetera envió (clave para enrutar al adaptador correcto)
- `title`: Título general (ej. "Interbank", "Confirmación de Pago")
- `content`: Mensaje completo con monto, destinatario, operación tipo
- `when`: Marca de tiempo de cuándo llegó

**Campos opcionales pero útiles:**
- `id`: Identificador numérico único
- `key`: Formato "paquete|id|null|cantidad" - útil para deduplicación
- `content`: Puede contener monto, nombre destinatario, tipo operación

### 13.3 Formato de Notificación JSON de Automate

Cuando Automate es el encargado de capturar y entregar la notificación, el JSON tiene esta estructura (mostrado como un solo registro, pero Automate puede entregar múltiple en secuencia):

```json
{
  "package": "pe.com.interbank.mobilebanking",    // Nombre paquete Android (CRÍTICO para enrutamiento)
  "title": "Interbank",                            // Título de la notificación
  "message": "Plineaste S/ 1.00 a Erick G Ramos A", // Cuerpo del mensaje
  "ticker_text": null,                             // Texto de la línea superior (a menudo null)
  "timestamp": 1795325030.526,                     // Marca de tiempo epoch en segundos
  "extras": {                                      // Paquete adicional de Android
    "android.title": "Interbank",
    "android.reduced.images": true,
    "android.subText": null,
    "android.showChronometer": false,
    "android.text": "Plineaste S/ 1.00 a Erick G Ramos A", // Mismo texto que "message"
    "android.progress": 0,
    "android.progressMax": 0,
    "android.showWhen": true,
    "android.infoText": null,
    "android.progressIndeterminate": false,
    "android.remoteInputHistory": null,
    "android.title": "Interbank",                    // Duplicado posible
    "android.text": "Plineaste S/ 1.00 a Erick G Ramos A" // Duplicado posible
  },
  "notification_id": "0|pe.com.interbank.mobilebanking|0|null|10404" // ID formateado
}
```

**Ejemplo múltiple (secuencia de notificaciones):**
Automate puede entregar múltiples notificaciones seguidas (ej. cuando un gasto dispara primero una pre-notificación y luego la confirmación):

```json
{
  "package": "pe.com.interbank.mobilebanking",
  "title": "Interbank",
  "message": "Plineaste S/ 60.00 a Anthony J Ruiz L",
  "ticker_text": null,
  "timestamp": 1794722156.001,
  "extras": {
    "android.title": "Interbank",
    "android.reduced.images": true,
    "android.text": "Plineaste S/ 60.00 a Anthony J Ruiz L",
    "android.progress": 0,
    "android.progressMax": 0,
    "android.showWhen": true,
    "android.infoText": null,
    "android.remoteInputHistory": null
  },
  "notification_id": "0|pe.com.interbank.mobilebanking|0|null|10404",
  "channel_id": "my_ibk_channel_ibk_0",
  "category": null,
  "removal_reason": null
}
```

**O Yape:**
```json
{
  "package": "com.bcp.innovacxion.yapeapp",
  "title": "Confirmación de Pago",
  "message": "Yape! LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON te envió un pago por S/ 40",
  "ticker_text": null,
  "timestamp": 1794722168.398,
  "extras": {
    "android.title": "Confirmación de Pago",
    "android.reduced.images": true,
    "android.template": "android.app.Notification$BigTextStyle",
    "android.subText": null,
    "android.showChronometer": False,
    "android.text": "Yape! LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON te envió un pago por S/ 40",
    "android.progress": 0,
    "androidx.core.app.extra.COMPAT_TEMPLATE": "androidx.core.app.NotificationCompat$BigTextStyle",
    "android.progressMax": 0,
    "android.showWhen": True,
    "android.largeIcon": None,
    "android.bigText": "Yape! LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON te envió un pago por S/ 40",
    "android.infoText": None,
    "android.remoteInputHistory": None,
    "android.colorized": True
  },
  "notification_id": "0|com.bcp.innovacxion.yapeapp|-574161335|null|10424",
  "channel_id": "default_notification_channel",
  "category": null,
  "removal_reason": null
}
```

### 13.3.1 Campos Críticos Compartidos por Ambos Formatos

| Campo | Formato Termux | Formato Automate | Descripción | Importancia |
|-------|---------------|-----------------|-------------|------------|
| `packageName` / `package` | ✅ | ✅ | Nombre paquete Android | **CRÍTICA** - Para identificar qué adaptador usar |
| `title` | ✅ | ✅ | Título de notificación | Alta - Identifica banco |
| `content` / `message` | ✅ | ✅ | Mensaje principal con operación | **CRÍTICA** - Monto, destinatario, tipo |
| `when` / `timestamp` | ✅ | ✅ | Marca de tiempo | Alta - Para ordenación FIFO y ventana consolidación |
| `key` / `notification_id` | ✅ (formato parcial) | ✅ (formato completo) | ID única de notificación | Media - Para deduplicación |
| `extras` | ❌ | ✅ | Contexto Android completo | Media - Metadata adicional |
| `group` / `group` | ❌ | ❌ | Grupo de notificación | Baja - Informacional |

### 13.4 Campos Extraídos a Diccionario Normalizado

Independientemente del formato origen (Termux o Automate), cada adaptador debe convertir los datos crudos a un diccionario estandarizado con estos campos obligatorios (definidos en la interfaz `BancoAdapter.normalizar_notificacion()`):

```python
normalizado = {
    "monto": float,              // Ej: 1.00, 60.00, 40.00 - SIEMPRE > 0
    "tipo": "ingreso" or "gasto", // Determinado por contenido del mensaje
    "destinatario": str,         // Ej: "Erick G Ramos A", "Anthony J Ruiz L", "LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON"
    "event_id": str,             // UUID generado o tomado de notification_id
    "canal": str,                // "yape", "plin", "bbva", "interbank", "nfc", "manual"
    "fecha_hora": str,           // ISO format o epoch convertido
    "mensaje_raw": str,          // El texto tal como llegó (para auditoría)
    "motivo": None,              // None - se solicitará al usuario después
    "fuente": "termux" or "automate"  // Para rastrear el origen
}
```

### 13.5 Lógica de Enrutamiento por Paquete

Los adaptadores usan el campo `packageName` (Termux) o `package` (Automate) para determinar qué adaptador invocar:

| Paquete / Package | Banco/Canal | Adaptador |
|------------------|-------------|-----------|
| `com.bcp.innovacxion.yapeapp` | Yape | `YapeAdapter` |
| `pe.com.interbank.mobilebanking` | Interbank | `IBKAdapter` |
| `com.bbva.bancomovil` | BBVA | `BBVAAdapter` |
| Paquetes NFC tag | NFC | `NFCAdapter` |
| Paquete manual entrada | Manual | `ManualAdapter` |
| Cualquier otro | Desconocido | `Dispatcher lanza warning, ignora o clasifica como ruido` |

### 13.6 Ejemplos de Extracción de Datos

#### Ejemplo 1: Notificación Interbank (Gasto)
**Termux input:**
```json
{
  "packageName": "pe.com.interbank.mobilebanking",
  "title": "Interbank",
  "content": "Plineaste S/ 1.00 a Erick G Ramos A",
  "when": "2026-11-22 00:23:50"
}
```
**Resultado normalizado:**
```python
{
    "monto": 1.00,
    "tipo": "gasto",
    "destinatario": "Erick G Ramos A",
    "canal": "interbank",
    "mensaje_raw": "Plineaste S/ 1.00 a Erick G Ramos A",
    "fecha_hora": "2026-11-22 00:23:50"
}
```

#### Ejemplo 2: Notificación Yape (Ingreso)
**Automate JSON:**
```json
{
  "package": "com.bcp.innovacxion.yapeapp",
  "title": "Confirmación de Pago",
  "message": "Yape! LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON te envió un pago por S/ 40",
  "timestamp": 1794722168.398,
  "extras": {
    "android.text": "Yape! LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON te envió un pago por S/ 40"
  }
}
```
**Resultado normalizado:**
```python
{
    "monto": 40.00,
    "tipo": "ingreso",
    "destinatario": "LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON",
    "canal": "yape",
    "mensaje_raw": "Yape! LUCAS ANDRE JUAQUIN VALDIVIESO BUTRON te envió un pago por S/ 40",
    "fecha_hora": "2026-11-22 00:??(del timestamp)"
}
```

#### Ejemplo 3: Detección de Tipo (Gasto vs Ingreso)
El adaptador debe analizar el `message`/`content` para determinar el tipo:
- Si contiene "te envió un pago" o "te transferenció" → `tipo: ingreso`
- Si contiene "Plineaste" o "gastaste" o "debité" → `tipo: gasto`
- Si es BBVA y requiere prompt → `tipo: indeterminado, solicitar al usuario`

### 13.6 Consideraciones para Adaptadores

Cada adaptador (`adaptadores/ibk.py`, `adaptadores/yape.py`, etc.) debe implementar un método `es_mis_notificacion()` que retorne `True` cuando el paquete coincida, y un método `normalizar_notificacion()` que:

1. **Parsee el monto** - Extraiga el número del mensaje (maneje formatos: "S/ 1.00", "S/ 40", "1.00", "$40")
2. **Identifique el tipo** - Analice palabras clave en el mensaje
3. **Extraiga el destinatario** - Nombre de persona/comercio que aparece después de "a" o "a "
4. **Genere event_id** - UUIDv4 si no viene en notification_id, o use el existente
5. **Preserve mensaje_raw** - Guarde el texto original para auditoría
6. **Maneje ausencias** - Si algún campo no se encuentra, use valores por defecto (monto 0.01, tipo "gasto", destinatario "desconocido")

### 13.7 Formato de Almacenamiento en SQLite

Una vez normalizado, el diccionario se inserta en la tabla `transacciones` con campos como:

```sql
INSERT INTO transacciones 
(id_transaccion, fecha_hora_epoch, fecha, hora, trimestre, app, paquete, dispositivo,
 tipo, medio, monto_total, moneda, destinatario, motivo, categoria, es_prestamo,
 monto_pagado, saldo_pendiente, estado_prestamo, looker, latitud, longitud, 
 fuente_gps, mensaje_raw, status, sincronizado, intentos_sync, ultimo_error_sync)
VALUES
(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, '');
```

Donde `mensaje_raw` guardaría el `content` (Termux) o `message` (Automate) original.

---

## 14. Migración de Datos y Formato Legacy

### 14.1 Notificaciones Antiguas (Pre-Arquitectura Hexagonal)
Si el sistema tiene notificaciones guardadas en formato anterior a la documentación actual, se recomienda:

1. **Ejecutar script de migración** (`scripts/migrar_notificaciones_legacy.py`)
2. **Convertir campos** a formato normalizado:
   - Antiguo: `cuerpo` → Nuevo: `mensaje_raw`
   - Antiguo: `nota_tipo` → Nuevo: `tipo` (ingreso/gasto)
   - Antiguo: `id_notificacion` → Nuevo: `event_id` (UUID)
3. **Validar duplicados** usando la ventana de consolidación
4. **Reindexar** la tabla `transacciones` si es necesario

### 14.2 Soporte para Nuevos Formatos de Bancos
A medida que salgan nuevas versiones de apps bancarias o nuevos bancos:
1. **Añadir adaptador** en `adaptadores/` siguiendo el patrón `BancoAdapter`
2. **Probar con samples** reales de notificaciones del nuevo banco
3. **Actualizar `config.yaml`** añadiendo el nombre paquete al listado `adaptadores_activos`
4. **No tocar código central** - la arquitectura hexagonal lo permite fácilmente

### 13.9 Checklist de Implementación de Adaptador de Notificaciones

Para crear un nuevo adaptador de banco, verificar:

- [ ] `es_mis_notificacion(paquete_terminx_o_automate)` retorna True para paq. correcto
- [ ] `normalizar_notificacion(datos_crudos)` retorna diccionario con todos campos obligatorios
- [ ] Manejo de formato de monto (con o sin símbolo S/, con o sin decimales)
- [ ] Detección correcta de tipo (ingreso vs gasto) por palabras clave
- [ ] Extracción correcta de destinatario (nombre que sigue a "a" o "a ")
- [ ] Generación o uso adecuado de event_id
- [ ] Preservación de mensaje_raw tal y como llegó
- [ ] Test con mínimo 3 samples reales de notificaciones del banco

---

**Documentación generada el:** 2026-11-22  
**Basado en samples reales:** Termux captures y JSON Automate mostrados por usuario
<tool_call>