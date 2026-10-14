# GUÍA PASO A PASO: CONFIGURACIÓN DE AZURE DEVOPS
## Cumplimiento de la Pauta de Evaluación (Criterios 8 al 15 — 100 Puntos)

**Proyecto:** Futbolito 7  
**Fecha Límite Final del Proyecto:** 18 de Diciembre  
**Entrega de esta Evaluación:** Archivo TXT con la URL del espacio de trabajo en Azure DevOps e invitación al docente.  

---

### 1. Definición Formal de Roles Scrum (Criterio 11 — 7 Puntos)

Asegúrate de que en la presentación y en la Wiki se mencionen formalmente estos roles:

* **Product Owner (PO):** **Eliezer Zenteno** (Define el alcance, prioriza las historias en el Product Backlog, aprueba los criterios de aceptación y es el contacto directo con el cliente/profesor).
* **Scrum Master (SM):** **Mario Carrasco** (Facilitador del equipo, asegura el cumplimiento del marco Scrum, monitorea la capacidad en horas, balancea la carga de trabajo y lidera las ceremonias).
* **Developers / Equipo de Desarrollo:**
  * **Paulo Alegría:** Backend Lead & Seguridad (Lógica de reservas, concurrencia, pagos y auditoría).
  * **Iván Alejandro:** Database Lead & Infraestructura (Modelado PostgreSQL, migraciones, settings e integraciones).
  * **Mario Carrasco:** Frontend & UX Lead (Diseño responsivo, maquetación Tailwind, componentes HTMX/Alpine).
  * **Eliezer Zenteno:** Full Stack & DevOps Lead (Pipelines CI/CD, configuración de repositorios y despliegue).

---

### 2. Configuración de Sprints en Azure DevOps (Criterio 8 y 13 — 15 Puntos)

En Azure DevOps, el creador del proyecto (Eliezer) o quien tenga permisos de configuración debe ir a:  
👉 **Project Settings > Project configuration > Iterations (Sprints)** y crear los siguientes 5 Sprints con fechas exactas:

| Nombre del Sprint | Fecha Inicio | Fecha Fin | Objetivo del Sprint |
|---|:---:|:---:|---|
| **Sprint 1: Fundamentos y Setup** | 01 Sep | 26 Sep | Configuración de entornos, repositorios, modelo relacional DER, wireframes y arquitectura base. |
| **Sprint 2: Canchas y Tarifas** | 28 Sep | 24 Oct | Modelado de Canchas, Complejos, tarifas punta/valle y grilla de disponibilidad con HTMX. |
| **Sprint 3: Reservas y Matchmaking** | 26 Oct | 21 Nov | Lógica de reservas concurrentes (`select_for_update`), lobby público 6v6 y políticas de cancelación. |
| **Sprint 4: Pagos y Recepción** | 23 Nov | 12 Dic | Integración de pasarela de pago, Split Payment en 12 cupos y panel operativo de turnos/check-in QR. |
| **Sprint 5: Auditoría y Cierre** | 14 Dic | **18 Dic** | Reportes contables con agregaciones ORM, auditoría con anonimización PII y despliegue final. |

> **Nota para el profesor:** El proyecto concluye exactamente el **18 de Diciembre** respetando la fecha tope académica.

---

### 3. Configuración de Capacidad y Feriados (Criterio 12 — 8 Puntos)
La pauta exige textualmente:
> *"La carga está distribuida de manera realista entre lunes y sábado, considerando disponibilidad y capacidad de cada integrante y excluyendo feriados irrenunciables."*

Para configurar esto en Azure DevOps:
1. Ir a **Sprints > pestaña Capacity** (arriba a la derecha, al lado de Taskboard y Backlog).
2. Para cada integrante (Mario, Eliezer, Paulo, Iván):
   - **Activity:** Asignar su rol (Development, Design, Requirements, Testing).
   - **Capacity per day:** Colocar entre **3.0 y 4.0 horas/día** (un estimado de 18 a 24 horas semanales por estudiante, lo cual es realista).
3. En la columna **Days off** de cada integrante (o a nivel de equipo en *Team days off*):
   - Añadir los feriados irrenunciables de Chile del semestre:
     - **18 de Septiembre** (Fiestas Patrias)
     - **19 de Septiembre** (Glorias del Ejército)
     - **31 de Octubre** (Día de las Iglesias Evangélicas)
     - **01 de Noviembre** (Día de Todos los Santos)
     - **08 de Diciembre** (Inmaculada Concepción)
4. Configurar los días laborables de lunes a sábado en **Project Settings > Team configuration > Working days** (marcar Monday, Tuesday, Wednesday, Thursday, Friday, Saturday).

---

### 4. Estimación de Horas en las Tasks (Criterio 10 y 14 — 20 Puntos)

Cada una de las Tasks que crearon tus compañeros debe tener estimación horaria. Al abrir una Task, en el panel lateral derecho (**Planning**):
- **Original Estimate:** ej. `4` (horas).
- **Remaining Work:** ej. `4` (horas).
- **Activity:** `Development` / `Design` / `Documentation`.

Al colocar las horas, el gráfico **Work details** de Azure DevOps mostrará una barra de capacidad en color verde para cada integrante, demostrando que la carga está perfectamente balanceada.

---

### 5. Lista de Verificación (Checklist) para el Día de la Presentación

- [ ] **Wiki actualizada:** Pegar el contenido del archivo `docs/WIKI_OFICIAL_FUTBOLITO7.md` en las páginas de la Wiki de Azure DevOps (Clientes, Usuarios, Requerimientos, Funcionalidades, Tecnologías, Arquitectura, Herramientas).
- [ ] **Invitación al docente:** Verificar que el profesor esté agregado como miembro en **Organization Settings > Users** o en el proyecto de Azure DevOps.
- [ ] **Archivo TXT para subir al portal:** Crear un archivo de texto con:
  ```
  PROYECTO: Futbolito 7 — Plataforma Web de Gestión y Reservas de Canchas
  URL ESPACIO DE TRABAJO AZURE DEVOPS:
  https://dev.azure.com/eliezerzenteno/Futbolito%207
  
  INTEGRANTES Y ROLES:
  - Eliezer Zenteno (Product Owner & Full Stack/DevOps)
  - Mario Carrasco (Scrum Master & Frontend/UX)
  - Paulo Alegría (Developer & Backend/Seguridad)
  - Iván Alejandro (Developer & Database/Infraestructura)
  ```
- [ ] **Mini presentación:** Mostrar:
  1. La **Wiki** (mostrar las tablas de tecnologías con versiones y el diagrama de arquitectura).
  2. Los **Sprints** (mostrar que están creados desde septiembre hasta el 18 de diciembre).
  3. La pestaña **Capacity** (mostrar los días de lunes a sábado, las horas por día y los días feriados excluidos).
  4. El **Taskboard** (mostrar que las tareas están asignadas con roles claros y horas estimadas).
