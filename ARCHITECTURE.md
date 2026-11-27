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

La Arquitectura Hexagonal (Ports and Adapters) está aplicada en la capa de procesamiento, separando la lógica de negocio de los detalles de implementación técnica.

**Capa Central:** Lógica de dominio y casos de uso relacionados con la captura, procesamiento y registro de transacciones financieras.

**Puertos (Interfaces):** Definiciones de contrato para operaciones clave como captura de notificaciones, persistencia de datos, obtención de ubicación, interacción con usuario y sincronización con servicios externos.

**Adaptadores:** Implementaciones técnicas que cumplen los puertos para bases de datos específicas (SQLite/PostgreSQL), proveedores de GPS, diálogos de usuario, y adaptadores por cada tipo de banco o servicio financiero.

**Configuración:** Un archivo de configuración centralizado (`config.yaml`) y variables de entorno definen el modo de operación, bancos activos, timeouts y credenciales de servicios externos.

**Flujo:** El sistema soporta múltiples modos de operación (configurables) para capturar notificaciones bancarias, procesarlas mediante los adaptadores correspondientes y registrar los resultados en almacenamiento local con opción de sincronización a la nube.

## 4. Modos de Operación Soportados

El sistema debe soportar DOS formas de captura de notificaciones, seleccionables desde el archivo `config.yaml`:

### Modo A: Automate File Broker
**Descripción:** El flujo principal actual donde Automate (Android) captura las notificaciones del banco y las escribe en un directorio configurado. Termux/Python procesa los archivos de este directorio en orden FIFO.

**Funcionamiento:** Automate detecta notificaciones push del banco y las guarda como archivos en un directorio específico. Termux detecta estos archivos nuevos y los procesa mediante su pipeline interno, enrutando cada una al adaptador bancario correspondiente, validando duplicados en ventana de tiempo, solicitando motivo al usuario si es necesario, obteniendo ubicación GPS y registrando la transacción en SQLite.

**Ventajas:** Ya probado y funcional en el proyecto; Automate captura notificaciones incluso cuando la app está cerrada; depuración más fácil al revisar los archivos en el directorio; compatible con la ventana de consolidación y el flujo FIFO existente.

**Desventajas:** Dependencia de que Automate escriba correctamente los archivos en el directorio configurado; implica un paso adicional en el flujo (automate → archivo → Termux).

### Modo B: Listener Directo
**Descripción:** Forma alternativa de captura donde Termux/Python escucha notificaciones push nativas de Android directamente, sin necesidad de que Automate escriba archivos intermedios.

**Funcionamiento:** Termux ejecuta un bucle de polling o usa listeners nativos de Android para capturar notificaciones push en tiempo real. Cada notificación se procesa inmediatamente al momento, sin necesidad de archivos intermediarios. El resto del pipeline (enrutamiento al adaptador, validación de duplicados, solicitud de motivo, obtención de GPS, inserción en SQLite y sincronización) es idéntico al modo Automate.

**Ventajas:** Flujo más directo con un paso menos (no requiere que Automate escriba archivos); procesamiento más en tiempo real; no depende de la configuración de archivos de Automate.

**Desventajas:** Requiere configuración adicional en Android (permissions, manifest, librerías); mayor consumo de batería al estar siempre escuchando notificaciones; más complejo de depurar en dispositivo real; Automate ya está instalado y configurado, no se necesita código extra en la app.

### Configuración del Modo
La selección del modo de operación se define en `config.yaml` mediante la propiedad `modo_operacion`. También se pueden configurar parámetros específicos para cada modo, como el directorio de archivos para el modo Automate o el intervalo de polling y la librería a usar para el modo Listener Directo.```

---

