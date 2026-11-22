# Gestor Offline-First de Gastos e Ingresos — Documentación Funcional y de Procesos (`README.md`)

Documentación integral a nivel de procesos, aplicaciones, casuísticas, comportamiento del sistema, estructura de datos e integraciones para la gestión de gastos e ingresos desde Android hacia SQLite local, Google Cloud Function, Google Sheets y Looker Studio.

---

## 1. Propósito y Enfoque del Sistema

El sistema centraliza y ordena todos los movimientos financieros personales (gastos, ingresos, pagos con tarjeta/NFC, transferencias, efectivo y préstamos/abonos) bajo un modelo **offline-first** y de **procesamiento secuencial en cola FIFO**.

Su objetivo principal es:
* Capturar movimientos sin perder información cuando el teléfono no tiene internet.
* Evitar registros duplicados cuando una misma operación dispara dos o más alertas consecutivas.
* Evitar preguntar dos veces al usuario por el mismo gasto o movimiento.
* Mantener trazabilidad de la ubicación geográfica donde ocurrió el movimiento.
* Entregar información limpia y estructurada para su análisis en Google Sheets y Looker Studio.

---

## 2. Ecosistema de Aplicaciones e Integraciones

* **Automate (Android):** Intercepta las notificaciones entrantes de las aplicaciones financieras y del sistema, y las entrega en orden de llegada (cola FIFO) al entorno de ejecución en Termux.
* **Termux + Python:** Ejecuta la lógica de enrutamiento, interpretación de alertas, consolidación en ventana de tiempo, solicitud de datos faltantes mediante diálogos (`termux-dialog`), captura de ubicación (`termux-location`), persistencia local y envío a la nube.
* **Base de Datos Local SQLite:** Almacena localmente las transacciones consolidadas, el historial de notificaciones crudas y el seguimiento de abonos de préstamos, permitiendo operar sin conexión y resolver duplicados o caídas de GPS.
* **Google Cloud Function:** Recibe los movimientos consolidados mediante un contrato JSON unificado y realiza la inserción/actualización idempotente en Google Sheets utilizando el identificador único de transacción.
* **Google Sheets:** Actúa como hoja de registro y respaldo en la nube, organizada con los campos operativos y analíticos del movimiento.
* **Looker Studio:** Consume los datos desde Google Sheets para visualizar gastos, ingresos, categorías, trimestres, medios de pago, préstamos y ubicaciones en el mapa.

---

## 3. Funcionamiento General y Comportamiento del Sistema

### 3.1 Cola FIFO y Procesamiento Secuencial
* Cada notificación capturada por Automate entra a una cola FIFO para procesarse en orden.
* El despachador identifica la aplicación o el tipo de evento y lo envía al proceso correspondiente.
* Si una notificación no corresponde a un movimiento válido o es ruido del sistema, se registra en la auditoría de notificaciones crudas como descartada/ignorada y se detiene sin molestar al usuario.

### 3.2 Consolidación en Ventana de Tiempo (Evitar Duplicidad y Doble Pregunta)
* Cuando un movimiento genera más de una alerta en un lapso breve (ventana de consolidación), el sistema busca en SQLite si ya existe un movimiento reciente compatible (por ejemplo, mismo tipo y mismo monto dentro de la ventana).
* **Si ya existe un registro reciente compatible:**
  * Se **consolida** la nueva notificación sobre ese mismo registro existente.
  * Se anexa la información nueva (por ejemplo, detalle de comercio, destinatario, medio o evidencia del mensaje crudo) si estaba incompleta.
  * **No se vuelve a pedir el motivo** al usuario ni se crea una segunda transacción.
* **Si no existe un registro previo compatible:**
  * Se trata como el primer evento de ese movimiento: se solicitan los datos faltantes al usuario (una sola vez), se obtiene la ubicación, se genera el identificador único de transacción y se guarda el registro consolidado.

### 3.3 Comportamiento de Ubicación (GPS con Respaldo)
* Al registrar un movimiento nuevo, el sistema intenta obtener las coordenadas actuales del celular (`termux-location`) con un tiempo de espera límite para no trabar la cola FIFO.
* **Si hay lectura GPS válida:** se guardan latitud, longitud, enlace de mapa y se marca el origen de ubicación como actual (`live`).
* **Si falla, hay error o vence el tiempo de espera:** se busca en SQLite la última coordenada válida registrada anteriormente (`last_known`). Si tampoco existe historial previo, se deja sin coordenadas (`none`).

### 3.4 Comportamiento Offline-First y Sincronización
* Todo movimiento se guarda primero en SQLite local con estado pendiente de sincronización (`sincronizado = 0`).
* Si el dispositivo tiene conexión a internet, se envía el paquete de datos a la Google Cloud Function.
* Si la nube responde de forma exitosa (`2xx`), el registro local se marca como sincronizado (`sincronizado = 1`).
* Si no hay internet o ocurre un fallo temporal, el dato queda seguro en SQLite y se reintenta más adelante sin generar duplicados.

---

## 4. Casuísticas por Aplicación y Canal

### 4.1 Yape
* **Ingresos por notificación:** Cuando llega una alerta de ingreso por Yape, se extrae el monto y remitente (si viene en el mensaje), se pide el motivo al usuario, se captura el GPS (con respaldo), se guarda en SQLite y se envía a la nube.
* **Egresos sin notificación:** Los pagos o salidas de dinero desde Yape que no emiten notificación automática se gestionan mediante el flujo manual.

### 4.2 Plin
* **Ingresos y gastos:** Procesa alertas de ingresos y gastos realizados por Plin.
* **Múltiples alertas / consolidación:** Puede ocurrir que un gasto por Plin dispare más de una alerta en corto tiempo (por ejemplo, una pre-notificación, la confirmación de Plin o una alerta asociada a tarjeta). Gracias a la búsqueda en SQLite dentro de la ventana de tiempo, todas se consolidan en un solo movimiento y el motivo se solicita una sola vez.

### 4.3 Interbank — Transferencias
* Procesa notificaciones de gastos por transferencia desde Interbank.
* Extrae los datos disponibles (monto, destinatario/detalle si figura), solicita el motivo al usuario, adjunta la ubicación GPS (con respaldo), guarda en SQLite y sincroniza con la Google Cloud Function.

### 4.4 Tarjeta Física y NFC (Enfoque Interbank y Tarjetas en General)
* Se maneja en un **único proceso unificado** para pagos con tarjeta física o NFC.
* **Casuística de orden no determinista en la cola FIFO:** Al pagar con NFC, puede llegar primero la notificación de NFC y luego la notificación de tarjeta/Interbank, o llegar primero la de Interbank y luego la de NFC.
  * Quien llegue **primero** crea el registro y pregunta el motivo **una sola vez**.
  * Quien llegue **segundo** encuentra el registro reciente en la ventana de SQLite y **se consolida** sin volver a preguntar el motivo ni duplicar el gasto.
* **Casuística de pago con tarjeta física (Interbank):** Sigue el mismo proceso unificado; si es la única alerta del gasto, registra el movimiento, pide el motivo y consolida cualquier confirmación adicional que llegue en ventana.
* **Casuística sin alerta bancaria (ej. tarjetas tipo Sodexo):** Solo entra el evento de NFC (si aplica) o se registra de forma manual si no hay notificación; se pide el motivo, se toma el GPS y se guarda sin esperar una alerta del banco.

### 4.5 BBVA (Ingresos y Gastos con Notificación Genérica)
* Las notificaciones de BBVA llegan sin detalle explícito en el texto (no indican claramente si es ingreso o gasto, ni monto, ni contraparte).
* Por ello, el proceso solicita de forma guiada al usuario (con tiempos de espera y validación):
  1. Tipo de movimiento (`Ingreso` o `Gasto`).
  2. Monto.
  3. Persona o comercio (destinatario/remitente).
  4. Motivo.
* Luego captura el GPS (con respaldo), guarda en SQLite y envía a la Google Cloud Function.

### 4.6 Compartamos Financiera (Solo Ingresos)
* Está enfocado exclusivamente en **ingresos** notificados por Compartamos Financiera (los gastos no generan notificación push y se atienden por el flujo manual).
* Valida que sea un ingreso, aplica resguardo contra duplicados recientes del mismo monto, extrae el monto y pide al usuario el **remitente/persona** y el **motivo**.
* Continúa con la captura de GPS (con respaldo), registro en SQLite y envío a la nube.

### 4.7 Movimientos Manuales (Efectivo y Otros Sin Notificación)
* Aplica para **efectivo** y cualquier otro gasto o ingreso que no genere notificación push (por ejemplo, egresos de Yape o gastos de Compartamos sin alerta).
* Se inicia directamente desde Termux (fuera de la cola de notificaciones).
* Solicita al usuario el tipo (`Gasto` o `Ingreso`), el monto, opcionalmente la persona o comercio, y el motivo.
* Incluye un resguardo contra doble toque accidental en ventana muy corta, obtiene el GPS (con respaldo), guarda en SQLite y sincroniza cuando hay conexión.

---

## 5. Proceso de Préstamos / Deudas y Abonos

Como los préstamos o deudas ocurren con poca frecuencia, el sistema evita hacer preguntas repetitivas en los movimientos diarios y opera bajo estas reglas:

1. **Registro de la deuda o préstamo (`Gasto`):**
   * Cuando prestas dinero o registras una deuda como salida de dinero, se crea un movimiento principal de tipo **Gasto** marcado como préstamo (`es_prestamo = 1`), con su monto total, monto pagado inicial en cero, saldo pendiente igual al monto total y estado de préstamo activo.
2. **Detección sin fricción:**
   * El sistema revisa palabras clave asociadas a préstamos o devoluciones en el texto del movimiento o del motivo (por ejemplo, términos vinculados a préstamo, adelanto, deuda, fiado, devolución, abono, cuota o reembolso) y verifica si existe un deudor con saldo pendiente.
   * Si no hay indicios ni coincidencias, no se abren diálogos adicionales.
3. **Registro de abonos o devoluciones (`Ingreso`):**
   * Cada vez que te devuelven dinero (total o parcialmente), el movimiento se registra como **Ingreso** en la tabla principal de transacciones para que el flujo de caja y los reportes en Google Sheets / Looker Studio reflejen el dinero recibido.
   * A su vez, ese abono se vincula al préstamo original para registrar el pago parcial, sumar al monto pagado, reducir el saldo pendiente y actualizar el estado del préstamo (activo, parcial o saldado al completarse).

---

## 6. Estructura de Datos y Tablas

El modelo de datos se organiza en **tres tablas** en SQLite, alineadas con los campos enviados a Google Cloud Function, Google Sheets y Looker Studio:

### 6.1 `transacciones` (Registro Principal Consolidado)
Representa el movimiento final único, limpio y listo para sincronizar hacia la nube:
* **Tiempo y organización:** Identificador único de transacción, marca de tiempo (epoch e ISO), fecha, hora y trimestre.
* **Origen y equipo:** Aplicación, paquete de Android y dispositivo.
* **Operación financiera:** Tipo (`Ingreso` / `Gasto`), medio (`Cuenta`, `Tarjeta`, `NFC`, `Efectivo`, etc.), monto total, moneda y destinatario/remitente/comercio.
* **Clasificación y préstamos:** Motivo, categoría, notas, indicador de préstamo, monto pagado, saldo pendiente, estado del préstamo y marcador de visibilidad para Looker Studio.
* **Ubicación y mensaje:** Latitud, longitud, enlace de mapa, fuente de ubicación (actual, última conocida o sin ubicación) y mensaje raw consolidado.
* **Control de proceso y nube:** Estado de consolidación, indicador de sincronizado, cantidad de intentos y último error de sincronización.

### 6.2 `notificaciones_crudas` (Auditoría de Notificaciones Entrantes)
Guarda cada notificación recibida desde Automate tal como llegó:
* Permite auditar qué alertas llegaron, en qué orden, a qué transacción consolidada se asociaron y qué ocurrió con cada una (insertada, consolidada en un registro existente, ignorada por duplicado o descartada como ruido).
* Mantiene una relación de **uno a muchos** con `transacciones`: una misma transacción consolidada puede agrupar una o varias notificaciones crudas.

### 6.3 `abonos_prestamo` (Historial de Devoluciones y Pagos Parciales)
Registra cada abono o devolución aplicado a un movimiento marcado como préstamo:
* Vincula el gasto/préstamo original con el movimiento de ingreso correspondiente al abono, guardando la fecha, el monto abonado, el saldo restante tras el pago y una nota descriptiva.
* Mantiene una relación de **uno a muchos** con `transacciones` (para los préstamos activos/parciales/saldados), permitiendo pagos en cuotas sin perder el detalle histórico ni alterar la lógica de ingresos/gastos.

### Índices de Consulta (Rendimiento)
Para mantener respuestas rápidas en el teléfono sin retrasar la cola FIFO, se contemplan índices enfocados en:
* Buscar candidatos recientes del mismo tipo y monto durante la ventana de consolidación.
* Localizar rápidamente registros pendientes de sincronizar (`sincronizado = 0`).
* Recuperar con rapidez la última ubicación válida registrada.
* Consultar préstamos abiertos o en seguimiento por persona/estado.
* Vincular notificaciones crudas con su transacción asociada.

---

## 7. Contrato de Datos Hacia la Nube (Google Cloud Function → Sheets → Looker)

* Cada transacción consolidada viaja en formato JSON hacia la Google Cloud Function incluyendo su identificador único de transacción (`id_transaccion`) y todos los campos de fecha, hora, trimestre, aplicación, paquete, dispositivo, tipo, medio, monto total, moneda, destinatario, motivo, categoría, notas, datos de préstamo/abono, indicador de Looker, ubicación/mapa, fuente GPS y mensaje raw.
* La Google Cloud Function utiliza el identificador único de transacción para hacer inserción o actualización idempotente en Google Sheets, evitando filas duplicadas ante reintentos de red.
* Looker Studio lee desde Google Sheets para construir los tableros de control financiero.

---

## 8. Orden Recomendado de Construcción

1. **Base de datos y servicios base:** Consolidar la base de datos local con sus tres tablas e índices, el manejo de diálogos y ubicación (con respaldo), y el sincronizador hacia Google Cloud Function.
2. **Canales directos:** Poner en marcha primero los flujos sin cruce de múltiples alertas (manual/efectivo, Yape y Compartamos) para probar de punta a punta hasta Google Sheets y Looker Studio.
3. **Canales con consolidación y captura guiada:** Incorporar Plin, Tarjeta Física/NFC (Interbank), Interbank Transferencias, BBVA y el despachador general.
