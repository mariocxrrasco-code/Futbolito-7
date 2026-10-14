# DOSSIER DE TRANSFERENCIA Y CONTEXTO MAESTRO: FUTBOLITO 7
**Para el Agente Antigravity en el Entorno Universitario**  
*Fecha de Emisión:* 22 de Septiembre, 2026  
*Autor:* Mario Carrasco (Scrum Master & Frontend/UX Lead)  

---

> ### ⚡ PROMPT DE INICIO RÁPIDO PARA EL ANTIGRAVITY DE LA UNIVERSIDAD
> **Si estás abriendo Antigravity por primera vez en el PC de la universidad, solo copia y pega este texto en el chat:**
> 
> *"Hola Antigravity. Asume el rol de Arquitecto de Software y Desarrollador Full Stack experto en Python, Django y Azure DevOps para nuestro proyecto **Futbolito 7**. Lee detalladamente el archivo `HANDOVER_CONTEXTO_ANTIGRAVITY.md` que está en la raíz de este proyecto para entender todo el contexto, stack de versiones, arquitectura modular, roles de nuestro equipo y el estado actual. Hoy comenzamos formalmente con el **Sprint 2: Desarrollo del Módulo y CRUD de Canchas, Complejos y Tarifas en Django**. Confírmame que comprendes todo y dime cuál es el primer paso técnico para codificar."*

---

## 1. Identidad, Visión y Propósito del Proyecto
* **Nombre del Proyecto:** Futbolito 7
* **Propósito:** Plataforma web monolítica modular para la digitalización integral de complejos deportivos comerciales de fútbol amateur (estilo Plaza 7 / Canchas Fútbol Pro). Automatiza el arriendo por bloques horarios de 60 minutos, control estricto de concurrencia pesimista sin sobreventa (*overbooking*), salas públicas de Matchmaking 6v6 con balanceo de equipos, pasarela de pago con división de cuenta (*Split Payment* de 12 cupos), panel de recepción con Check-in QR y auditoría con privacidad de datos (enmascaramiento PII).
* **Fecha Límite Final de Entrega:** **18 de Diciembre de 2026**.

---

## 2. Equipo de Trabajo y Roles Scrum Formales
Somos un equipo de 4 integrantes con roles claramente asignados en **Azure DevOps**:
1. **Eliezer Zenteno Manríquez:** Product Owner (PO) & Full Stack / DevOps Lead. (Administrador de la organización en Azure DevOps: `https://dev.azure.com/eliezerzenteno/Futbolito%207`).
2. **Mario Carrasco Calderón:** Scrum Master (SM) & Frontend / UI-UX Lead. (Gobernanza ágil, maquetación Tailwind CSS, componentes HTMX y plantillas).
3. **Paulo Alegría Díaz:** Development Team — Backend & Security Lead. (Lógica de reservas, concurrencia `select_for_update`, algoritmos y privacidad PII).
4. **Iván Alejandro:** Development Team — Database & Infrastructure Lead. (Modelado relacional PostgreSQL 16, driver Psycopg 3, ORM y endpoints DRF).

---

## 3. Stack Tecnológico Obligatorio y Versiones Oficiales
*(Importante: Estas son las versiones exactas pactadas en la arquitectura y defendidas ante el docente; no cambiarlas sin justificación)*:

| Componente | Tecnología | Versión Oficial | Propósito en el Proyecto |
|---|---|:---:|---|
| **Lenguaje Backend** | Python | `3.11+ / 3.12` | Lógica de negocio, servicios y algoritmos de balanceo. |
| **Framework Web** | Django | `6.1` | Arquitectura monolítica modular, ORM, autenticación y admin. |
| **APIs y Serialización** | Django REST Framework (DRF) | `3.18.0` | Endpoints JSON para componentes dinámicos y móvil. |
| **Driver de Base de Datos** | Psycopg 3 (`psycopg[binary]`) | `3.3` | Driver moderno de conexión asíncrona a PostgreSQL. |
| **Motor de Base de Datos** | PostgreSQL | `16.x` | Base de datos relacional con transaccionalidad ACID y bloqueo pesimista. |
| **Filtrado Declarativo** | django-filter | `26.1` | Filtrado dinámico de canchas, fechas y disponibilidad horaria. |
| **Variables de Entorno** | django-environ | `0.14.0` | Configuración segura `.env` bajo metodología Doce Factores. |
| **Procesamiento de Fotos** | Pillow | `12.3.0` | Optimización y recorte de imágenes de canchas y comprobantes. |
| **Maquetación Frontend** | Tailwind CSS | `3.4+` | Diseño responsivo utility-first enfocado en dispositivos móviles. |
| **Interactividad Asíncrona** | HTMX | `1.9+` | Peticiones asíncronas y recargas parciales de HTML sin JavaScript pesado. |
| **Componentes de Cliente** | Alpine.js | `3.x` | Modales, temporizadores regresivos (countdown) y lógica de interfaz liviana. |
| **Control de Versiones y CI/CD** | Git + Azure DevOps | `Cloud` | Azure Repos (GitFlow), Azure Boards, Azure Pipelines y Wiki. |

---

## 4. Arquitectura Modular de Django (Estructura de Carpetas)
La solución sigue una arquitectura monolítica modular desacoplada en aplicaciones dentro del directorio `apps/`:

```
futbolito7/
├── manage.py
├── .env                     # Variables de entorno (SECRET_KEY, DATABASE_URL, DEBUG)
├── .gitignore               # Configurado para Python, venv, estáticos y .env
├── requirements.txt         # Dependencias con versiones fijadas
├── config/                  # Configuración raíz del proyecto
│   ├── __init__.py
│   ├── settings.py          # Configuración modular (Base, Database, Templates)
│   ├── urls.py              # Enrutador principal de URLs
│   ├── wsgi.py
│   └── asgi.py
├── apps/                    # Módulos desacoplados del sistema
│   ├── core/                # Vistas base, layout general, home y mixins
│   ├── accounts/            # Custom User model (Jugador, Recepcionista, Dueño)
│   ├── canchas/             # Modelos: Complejo, Cancha, Superficie, Tarifa (Punta/Valle)
│   ├── reservas/            # Modelos: BloqueHorario, Reserva (select_for_update)
│   ├── matchmaking/         # Modelos: PartidoMatchmaking (6v6), salas y cupos
│   ├── pagos/               # Modelos: Pago, SplitPayment (12 cupos) y Pasarela
│   └── auditoria/           # Modelo AuditLog y Middleware de anonimización PII
├── templates/               # Plantillas Django
│   ├── base.html            # Layout maestro con Tailwind CSS, HTMX y Alpine.js
│   ├── includes/            # Navbar, footer, alertas
│   └── canchas/             # Vistas de catálogo y administración de canchas
├── static/                  # Archivos estáticos (CSS, JS, imágenes)
└── media/                   # Archivos subidos por usuarios (fotos de canchas vía Pillow)
```

---

## 5. Reglas de Negocio Críticas que el Agente DEBE Respetar
1. **Control de Concurrencia Pesimista (Anti-Overbooking):**
   - Dos usuarios jamás pueden reservar la misma cancha en el mismo bloque horario.
   - Toda reserva debe ejecutarse dentro de un bloque `transaction.atomic()` utilizando `select_for_update()` en PostgreSQL sobre la fila de `BloqueHorario`.
   - Se aplica un bloqueo temporal de **10 minutos** en estado `"En Proceso de Pago"`. Si el pago no se completa, un proceso de background o comprobación de timestamp libera la cancha a estado `"Disponible"`.
2. **Tarifas Diferenciadas (Punta vs. Valle):**
   - *Horario Valle (Lunes a Viernes de 09:00 a 17:00 hrs):* Tarifa promocional diurna (ej. \$24.000 a \$26.000 CLP).
   - *Horario Punta (Lunes a Viernes de 18:00 a 23:00 hrs, Sábados y Domingos completos):* Tarifa estándar de alta demanda (ej. \$36.000 a \$42.000 CLP).
3. **Matchmaking 6v6 y Armado de Equipos:**
   - Salas públicas para completar 12 cupos individuales (\$3.500 c/u).
   - Al inscribirse el cupo 12, se cierra la sala y un algoritmo en Python distribuye y balancea aleatoriamente a los 12 jugadores en **Equipo A (6)** y **Equipo B (6)**.
4. **Split Payment (División de Pagos):**
   - El capitán puede optar por pagar el 100% de la cancha o dividir el costo en 12 cupos.
   - El sistema genera un token de enlace único para compartir por WhatsApp con temporizador de caducidad de **12 horas**.
5. **Panel de Turnos en Recepción y Check-in QR:**
   - La recepción dispone de un panel diario en vivo para escanear el código QR del partido o validar asistencia manual, además de registrar cobros directos en caja (efectivo/transferencia bancaria).
6. **Auditoría con Anonimización PII:**
   - Toda acción sensible (reserva, pago manual, anulación) queda registrada en `AuditLog`.
   - Los datos personales sensibles (RUT, teléfonos y correos) deben guardarse anonimizados o enmascarados (ej. `m***o@correo.cl`).

---

## 6. Horizonte de Sprints y Planificación en Azure DevOps
* **Jornada de Trabajo:** Lunes a Sábado (3.5 horas/día promedio por integrante = 21 hrs semanales por persona).
* **Feriados Irrenunciables Excluidos:** 18-19 de Septiembre, 31 de Octubre, 01 de Noviembre, 08 de Diciembre.
* **Cronograma:**
  - **Sprint 1 (01 Sep – 26 Sep):** Setup, Fundamentos, DER, Wireframes y Requerimientos. *(Completado / Evaluado)*.
  - **Sprint 2 (28 Sep – 24 Oct) [FASE ACTUAL]:** Módulo Canchas, Tarifas Diferenciadas y Calendario HTMX.
  - **Sprint 3 (26 Oct – 21 Nov):** Motor de Reservas con `select_for_update`, Matchmaking 6v6 y Cancelaciones.
  - **Sprint 4 (23 Nov – 12 Dic):** Integración Pasarela de Pagos (Webpay/Stripe), Split Payment 12 cupos y Panel de Recepción QR.
  - **Sprint 5 (14 Dic – 18 Dic):** Auditoría PII, Reportes Financieros con agregaciones ORM, CI/CD en Azure Pipelines y Entrega Definitiva (18 Dic).

---

## 7. Estado Actual y Tarea Inmediata de Hoy
* **Hito alcanzado:** Toda la etapa de planificación, Wiki oficial de 7 páginas, matriz de requerimientos IEEE 830, prototipo interactivo de wireframes y configuración de Azure DevOps fue presentada y evaluada exitosamente.
* **Siguiente Paso Técnico Inmediato (Sprint 2 - Módulo Canchas y Complejos):**
  1. Estructurar el proyecto Django (`manage.py`, `config/settings.py` con `django-environ` y conexión a PostgreSQL).
  2. Implementar los modelos de la app `apps/canchas`:
     - Modelo `Complejo` (nombre, dirección, comuna, teléfono, activo).
     - Modelo `Superficie` (Pasto Sintético, Techada, Aire Libre, Caucho).
     - Modelo `Cancha` (complejo FK, número/nombre, superficie FK, precio_base, foto con Pillow).
     - Modelo `Tarifa` (cancha FK, tipo_horario: Valle/Punta, dia_semana, hora_inicio, hora_fin, precio_bloque).
  3. Registrar los modelos en el Django Admin con interfaz estilizada y filtros.
  4. Crear vistas y endpoints iniciales de consulta de canchas para el frontend.
