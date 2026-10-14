# WIKI OFICIAL DEL PROYECTO: FUTBOLITO 7
**Plataforma Web de Gestión y Reservas para Complejos Deportivos**  
*Repositorio y Gestión: Azure DevOps (Proyecto Futbolito 7)*  
*Fecha de Entrega Final:* 18 de Diciembre  
*Versión Documental:* 2.0 (Planificación Integral)  

---

## 1. Cliente Objetivo (Criterio 1 - Pauta)
* **Definición del Cliente:** Dueños, administradores y sociedades operadoras de complejos deportivos comerciales de fútbol amateur (canchas de futbolito 5v5, 6v6 y 7v7, pasto sintético y canchas techadas), cuyo modelo de negocio se basa en el arriendo por bloques horarios.
* **Contexto y Características:**
  - Operan de lunes a domingo en horarios de alta demanda (18:00 a 23:00 hrs) y horarios valle diurnos.
  - Cuentan con infraestructura de 2 a 8 canchas por recinto.
  - Presentan alta rotación de clientes y pagos informales.
* **Necesidades Principales del Negocio:**
  1. **Eliminar el solapamiento de horarios (overbooking):** Evitar reclamos y conflictos por doble arriendo gestionado vía llamadas o mensajería (WhatsApp).
  2. **Maximizar la tasa de ocupación:** Incentivar el arriendo en horarios diurnos/valle mediante tarifas dinámicas diferenciadas.
  3. **Asegurar la recaudación y reducir la morosidad:** Cobro anticipado total o garantizado mediante división de pagos (*Split Payment*).
  4. **Trazabilidad y control contable:** Disponer de métricas consolidadas de ingresos por cancha, medios de pago y turnos atendidos sin descuadres de caja.

---

## 2. Usuarios de la Solución (Criterio 2 - Pauta)

| Perfil de Usuario | Rol en el Sistema | Responsabilidades y Acciones Clave | Nivel de Interacción |
|---|---|---|:---:|
| **Jugador / Cliente** | Usuario Final Externo | - Consulta disponibilidad de canchas en tiempo real.<br>- Reserva bloques horarios y realiza pago en línea (Total o Split).<br>- Crea o se une a salas públicas de Matchmaking 6v6.<br>- Presenta código QR en recepción para validación. | Alta (Web Móvil / Desktop) |
| **Operador de Turno / Recepcionista** | Usuario Staff Operativo | - Monitorea en vivo la grilla de turnos diarios.<br>- Valida check-in presencial (escaneo QR o manual).<br>- Registra cobros en efectivo/transferencia presencial.<br>- Aplica bloqueos de emergencia por contingencias (lluvia/mantenimiento). | Continua (Panel Desktop en Recepción) |
| **Administrador / Dueño del Complejo** | Superusuario / Gestor | - Configura tarifas diferenciadas (Punta vs. Valle) y canchas.<br>- Consulta dashboards financieros (ingresos brutos, tasas de uso).<br>- Supervisa el cumplimiento de políticas de cancelación.<br>- Audita operaciones y trazabilidad del sistema. | Media / Estratégica (Dashboard Gerencial) |
| **Sistema / Tareas Automáticas** | Actor Automatizado | - Libera bloques temporales impagos tras 10 minutos.<br>- Ejecuta el algoritmo de balanceo de equipos al llenarse los 12 cupos 6v6.<br>- Aplica enmascaramiento de datos personales en logs de auditoría. | Backend Asíncrono |

---

## 3. Requerimientos Funcionales y No Funcionales (Criterio 3 - Pauta)

### Requerimientos Funcionales (RF):
* **RF-01 (Gestión de Canchas):** El sistema debe permitir catalogar canchas con características físicas (superficie, techada/aire libre, iluminación) y estado operativo.
* **RF-02 (Reserva por Bloques Horarios):** El sistema debe permitir el agendamiento en bloques de 60 minutos con control de concurrencia pesimista (`select_for_update`) para evitar colisiones.
* **RF-03 (Tarifas Diferenciadas):** El sistema debe aplicar tarifas dinámicas configurables: Horario Valle (diurno) y Horario Punta (nocturno y fines de semana).
* **RF-04 (Matchmaking 6v6):** El sistema debe permitir crear salas abiertas de 12 cupos individuales y balancear automáticamente a los jugadores en Equipo A (6) y Equipo B (6).
* **RF-05 (Pagos y Split Payment):** El sistema debe soportar pago total inmediato (100%) o generación de 12 enlaces de pago compartido con expiración automática.
* **RF-06 (Cobros Presenciales):** El operador debe poder registrar pagos manuales en recepción (efectivo/transferencia) actualizando la reserva.
* **RF-07 (Políticas de Cancelación):** El sistema debe permitir reprogramar o anular reservas con tiempo mínimo (ej. 4 horas antes), liberando el bloque.
* **RF-08 (Check-in y Turnos):** El sistema debe proveer validación de asistencia en cancha mediante código QR o búsqueda por titular.
* **RF-09 (Métricas Contables):** El sistema debe calcular ingresos brutos por cancha, horas de mayor demanda y porcentaje de ocupación mensual.
* **RF-10 (Auditoría con Privacidad PII):** El sistema debe registrar toda acción crítica en `AuditLog`, enmascarando datos personales sensibles (RUT, teléfonos, correos).

### Requerimientos No Funcionales (RNF):
* **RNF-01 (Rendimiento):** Tiempos de respuesta menores a 300 ms en recargas parciales del calendario.
* **RNF-02 (Concurrencia y Consistencia):** Transacciones ACID en PostgreSQL con nivel de aislamiento que impida carreras críticas (*race conditions*).
* **RNF-03 (Seguridad):** Protección activa contra CSRF, inyecciones SQL (Django ORM) y control de acceso basado en roles (RBAC).
* **RNF-04 (Privacidad de Datos):** Cumplimiento de estándares de protección de datos personales; ningún dato sensible se almacena en texto plano en logs.
* **RNF-05 (Disponibilidad):** Manejo de tolerancia a fallos y timeouts automáticos de reservas pendientes.
* **RNF-06 (Responsividad):** Diseño adaptable 100% responsivo para navegación fluida en dispositivos móviles y de escritorio.

---

## 4. Funcionalidades del Sistema (Criterio 4 - Pauta)

1. **Calendario Semanal Interactivo:**
   - *Propósito:* Visualizar la disponibilidad por cancha y hora sin recargar la página completa.
   - *Relación con Requerimientos:* Satisface **RF-02** y **RF-03**.
2. **Mecanismo de Reserva Concurrente:**
   - *Propósito:* Bloqueo temporal por 10 minutos mientras el cliente completa el pago, evitando reservas dobles.
   - *Relación con Requerimientos:* Satisface **RF-02** y **RNF-02**.
3. **División de Cuentas (Split Payment):**
   - *Propósito:* Facilitar el pago en grupo para fútbol amateur generando 12 cuotas individuales para WhatsApp.
   - *Relación con Requerimientos:* Satisface **RF-05**.
4. **Lobby de Partidos Abiertos (Matchmaking 6v6):**
   - *Propósito:* Permitir a jugadores sin equipo completar partidos y recibir su asignación de camiseta/equipo.
   - *Relación con Requerimientos:* Satisface **RF-04**.
5. **Panel Operativo de Turnos en Vivo:**
   - *Propósito:* Dotar a la recepción de una vista cronológica para chequear llegadas y registrar cobros en caja.
   - *Relación con Requerimientos:* Satisface **RF-06** y **RF-08**.
6. **Dashboard Financiero y Estadístico:**
   - *Propósito:* Apoyar la toma de decisiones del dueño mediante reportes de recaudación y ocupación.
   - *Relación con Requerimientos:* Satisface **RF-09**.
7. **Motor de Auditoría y Privacidad:**
   - *Propósito:* Registrar qué usuario hizo qué cambio, manteniendo protegida la privacidad de los clientes.
   - *Relación con Requerimientos:* Satisface **RF-10** y **RNF-04**.

---

## 5. Tecnologías y Versiones Utilizadas (Criterio 5 - Pauta)

| Tecnología / Paquete | Versión Oficial | Propósito en la Solución | Justificación Técnica |
|---|:---:|---|---|
| **Python** | `3.11+ / 3.12` | Lenguaje de programación base del backend. | Robustez, tipado, madurez del ecosistema y alto desempeño para lógica de negocio. |
| **Django** | `6.1` | Framework web principal (arquitectura monolítica modular). | Provee ORM seguro, motor de plantillas, autenticación de usuarios y administración integrada. |
| **Django REST Framework (DRF)** | `3.18.0` | Creación de endpoints y serialización de datos. | Permite exponer servicios REST limpios para interacciones dinámicas y futuras integraciones móviles. |
| **Psycopg 3** | `3.3` (`psycopg[binary]`) | Driver conector entre Django y PostgreSQL. | Driver moderno para PostgreSQL con soporte nativo para conexiones asíncronas y tipado eficiente. |
| **PostgreSQL** | `16.x` | Motor de Base de Datos Relacional. | Garantiza transacciones ACID, soporte para bloqueos de fila (`FOR UPDATE`) y consistencia absoluta en reservas. |
| **django-filter** | `26.1` | Motor de filtrado dinámico en consultas ORM. | Facilita el filtrado declarativo por canchas, fechas y rangos horarios en el calendario y reportes. |
| **django-environ** | `0.14.0` | Gestión de variables de entorno según doce factores. | Desacopla credenciales y configuraciones sensibles del código fuente (`.env`), vital para Azure Pipelines. |
| **Pillow** | `12.3.0` | Procesamiento y manipulación de imágenes. | Gestión y optimización de imágenes de las canchas, comprobantes y avatares de usuarios. |
| **Django Templates + Tailwind CSS** | `3.4+` | Maquetación y diseño responsivo del frontend. | Interfaz moderna estilo utility-first, liviana, adaptable a móviles sin sobrecarga de frameworks JS pesados. |
| **HTMX & Alpine.js** | `HTMX 1.9+ / Alpine 3.x` | Reactividad asíncrona en cliente y modales livianos. | Permite actualizar el calendario y formularios sin recargar la página, reduciendo drásticamente la complejidad. |

---

## 6. Arquitectura del Sistema (Criterio 6 - Pauta)

La plataforma adopta una **Arquitectura Monolítica Modular en Capas**, garantizando alta cohesión y bajo acoplamiento entre módulos:

```
+-------------------------------------------------------------------------+
|                         CAPA DE PRESENTACIÓN                            |
|     Django Templates + Tailwind CSS + HTMX (Reactividad Asíncrona)      |
|               Navegador Móvil (Jugador) / Desktop (Recepción)           |
+-------------------------------------------------------------------------+
                                    | HTTP / JSON / HTML Partials
                                    v
+-------------------------------------------------------------------------+
|                         CAPA LÓGICA DE NEGOCIO                          |
|                       Framework Django 6.1 + DRF 3.18                   |
|  +----------------+ +----------------+ +----------------+ +-----------+ |
|  |  apps/canchas  | |  apps/reservas | |apps/matchmaking| |apps/pagos | |
|  +----------------+ +----------------+ +----------------+ +-----------+ |
|  +--------------------------------------------------------------------+ |
|  | Middleware de Seguridad, Protección CSRF y Auditoría PII Masking   | |
+-------------------------------------------------------------------------+
                                    | ORM (Consultas & Transacciones)
                                    v
+-------------------------------------------------------------------------+
|                         CAPA DE PERSISTENCIA                            |
|             Driver Psycopg 3.3  -->  PostgreSQL 16 (ACID)               |
|            Control de Concurrencia con "SELECT ... FOR UPDATE"          |
+-------------------------------------------------------------------------+
```

### Flujo de Datos para una Reserva Concurrente:
1. El usuario selecciona un bloque libre en el calendario y envía la petición vía **HTMX**.
2. La vista en `apps/reservas` abre una transacción atómica en Django (`transaction.atomic()`).
3. El ORM invoca `select_for_update()` sobre el bloque horario en **PostgreSQL**, bloqueando la fila a nivel de base de datos.
4. Si está libre, se genera un estado `"En Proceso de Pago"` por 10 minutos y se retorna la vista del formulario.
5. Al completarse el pago, se confirma la reserva y el middleware de auditoría registra la acción con datos personales enmascarados.

---

## 7. Herramientas de Desarrollo y Gestión (Criterio 7 - Pauta)

| Ámbito | Herramienta Oficial | Justificación y Modo de Utilización |
|---|---|---|
| **Gestión Ágil y Backlog** | **Azure Boards** | Planificación de Sprints, creación de Epics, Issues y Tasks, estimación de horas y balanceo de capacidad. |
| **Control de Versiones** | **Git + Azure Repos** | Control de código fuente con flujo de ramas (*GitFlow*: `main`, `develop`, `feature/*`), Pull Requests y revisiones de código. |
| **Integración y Despliegue** | **Azure Pipelines** | Automatización de pruebas unitarias (`pytest`/`django test`), análisis de código y preparación de despliegue continuo (CI/CD). |
| **Documentación y Wiki** | **Azure DevOps Wiki** | Repositorio centralizado de especificación de requerimientos, arquitectura, minutas y guías de instalación. |
| **Entorno de Desarrollo (IDE)** | **Visual Studio Code / PyCharm** | Entorno estándar para codificación en Python, extensiones de Django, formateo con Black/Flake8 y debugging. |
| **Diseño y Prototipado** | **draw.io & Figma** | Modelado de diagramas UML/DER, diagramas de arquitectura y wireframes de interfaces de usuario. |
| **Pruebas de API** | **Postman / Thunder Client** | Verificación de respuestas de endpoints REST, headers de seguridad y pruebas de carga básica. |
| **Comunicación de Equipo** | **Discord & Microsoft Teams** | Reuniones diarias (Daily Standups), coordinación de Sprint Planning y retroalimentación con el docente. |
