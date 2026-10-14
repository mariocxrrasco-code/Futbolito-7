# CONTEXTO DEL PROYECTO: FUTBOLITO 7
Este archivo es consumido automáticamente por Google Antigravity para mantener el contexto del proyecto entre distintos entornos y sesiones de trabajo.

## 1. Identidad y Propósito
- **Proyecto:** Futbolito 7 — Plataforma Web de Gestión y Reservas para Complejos Deportivos de Fútbol Amateur.
- **Arquitectura:** Monolito modular con Python / Django 6.1 + PostgreSQL 16 + Tailwind CSS + HTMX + Alpine.js.
- **Horizonte Académico:** Entrega final el 18 de Diciembre de 2026.
- **Gestión:** Azure DevOps (Azure Boards, Azure Repos, Azure Pipelines y Wiki).

## 2. Equipo y Roles Scrum
- **Eliezer Zenteno:** Product Owner (PO) & Full Stack / DevOps Lead.
- **Mario Carrasco:** Scrum Master (SM) & Frontend / UI-UX Lead.
- **Paulo Alegría:** Backend & Security Lead (Concurrencia, Pagos y Auditoría PII).
- **Iván Alejandro:** Database & Infrastructure Lead (PostgreSQL 16, Modelado DER y DRF).

## 3. Stack Tecnológico Obligatorio y Versiones Exactas
- **Python:** 3.11+ / 3.12
- **Django:** 6.1 (Monolito modular con apps desacopladas en `apps/`)
- **Django REST Framework (DRF):** 3.18.0
- **Base de Datos:** PostgreSQL 16
- **Driver de BD:** Psycopg 3 (`psycopg[binary] 3.3`)
- **django-filter:** 26.1
- **django-environ:** 0.14.0
- **Pillow:** 12.3.0
- **Frontend:** Django Templates + Tailwind CSS 3.4+ + HTMX 1.9+ + Alpine.js 3.x

## 4. Reglas de Negocio Clave
1. **Control de Concurrencia:** Bloqueo pesimista con `select_for_update()` en transacciones atómicas de PostgreSQL sobre `BloqueHorario` para evitar solapamiento de arriendos (*overbooking*). Bloqueo temporal por 10 minutos.
2. **Tarifas Diferenciadas:** Precios dinámicos por franja horaria: Horario Valle (diurno, lunes a viernes) vs Horario Punta (nocturno y fines de semana).
3. **Matchmaking 6v6:** Salas públicas de 12 cupos individuales con algoritmo en Python de balanceo aleatorio de equipos (Equipo A vs Equipo B).
4. **Split Payment:** División del arriendo total en 12 cupos mediante enlaces individuales para compartir por WhatsApp con temporizador de 12 horas.
5. **Panel de Recepción:** Check-in presencial con escaneo de código QR y registro de cobros manuales (efectivo/transferencia).
6. **Auditoría PII:** Registro en modelo `AuditLog` con enmascaramiento obligatorio de datos personales sensibles (RUT, teléfonos, correos).

## 5. Estado Actual: Inicio del Sprint 2 (Desarrollo del CRUD)
- Sprint 1 (Planificación, DER, Wireframes y Requerimientos) completado y evaluado.
- **Sprint 2 en curso:** Desarrollo de modelos Django de la app `apps/canchas` (`Complejo`, `Cancha`, `Superficie`, `Tarifa`), configuración de `settings.py` con `django-environ`, registro en el Django Admin y vistas/endpoints iniciales.

Para más detalle operativo y comandos de inicio rápido, consultar `HANDOVER_CONTEXTO_ANTIGRAVITY.md`.

## 6. Eficiencia de Tokens y Comunicación (Always-On)
- **Directo al código/solución:** Sin rodeos, introducciones innecesarias ni explicaciones repetitivas.
- **Inspección quirúrgica:** Leer archivos por bloques específicos con `view_file` (usando `StartLine` y `EndLine`).
- **Edición modular:** Modificar únicamente las líneas exactas con `replace_file_content`, nunca sobreescribir archivos enteros si no es imprescindible.
