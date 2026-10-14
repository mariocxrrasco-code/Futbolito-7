# GUÍA OFICIAL PARA LA DEMOSTRACIÓN EN VIVO (DOCENTE)
**Proyecto:** Futbolito 7 — Plataforma Web de Gestión y Reservas de Alta Concurrencia  
**Equipo Scrum:** Eliezer Zenteno (PO), Mario Carrasco (SM/UX), Paulo Alegría (Backend/Seguridad), Iván Alejandro (BD/Infra)

---

## 1. Demostración de Funcionalidad Representativa (100%)

### A. Grilla Visual Interactiva (Frontend Tailwind CSS)
1. Iniciar el servidor local (si no estuviese activo):
   ```bash
   .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
   ```
2. Abrir en el navegador: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
3. **Puntos clave a mostrar al profesor:**
   - **Diseño Moderno & Responsivo:** Tema oscuro deportivo con contrastes esmeralda, tipografía Outfit e Inter, y badges dinámicos.
   - **Tarifas Diferenciadas:** Mostrar cómo los bloques diurnos tienen etiqueta `🌱 Valle ($30.000 CLP)` y los nocturnos / fines de semana tienen `⚡ Punta ($42.000 CLP)`.
   - **Selector de Fechas Reactivo:** Cambiar entre *Hoy*, *Mañana*, *+2 Días* y ver la actualización instantánea de disponibilidad vía API JSON.
   - **Reserva Interactiva:** Clic en un bloque verde "Reservar", completar el formulario modal y presionar "Confirmar Reserva".
   - **Comprobante y Protección PII (ISO 27034):** Mostrar el comprobante generado con el código UUID y los datos sensibles enmascarados (`m***o@correo.cl`, `+569 **** 4321`).

### B. Control de Concurrencia Pesimista en Vivo (Regla R-01 Anti-Overbooking)
1. En la grilla principal, hacer clic en el botón superior:
   > **`⚡ Demo Concurrencia R-01 (Docente)`**
2. **Lo que ocurre tras bambalinas:**
   - El sistema dispara **2 peticiones HTTP paralelas en el mismo milisegundo** intentando reservar el mismo bloque horario.
   - El motor Django ejecuta `select_for_update()` a nivel de fila en la transacción de base de datos.
   - **Resultado en pantalla:** La primera transacción es aprobada (`HTTP 201 Created`) y la segunda es rechazada con `HTTP 409 Conflict` con el mensaje:
     > *"Conflicto de Concurrencia (ISO 27034 R-01): La cancha ya fue reservada por otro usuario. OVERBOOKING_PREVENTED"*.
   - Se demuestra de forma irrefutable que **es imposible la sobreventa**.

### C. Panel de Administración Django
1. Acceder a [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
2. Credenciales creadas:
   - **Usuario:** `admin`
   - **Contraseña:** `AdminFutbolito7!`
3. Mostrar los módulos:
   - **Canchas:** Complejos, Superficies, Canchas con precios base y Tarifas Horarias.
   - **Reservas:** Bloques Horarios con badges visuales de color (Verde/Ámbar/Gris) y Reservas con columnas protegidas PII.

---

## 2. Demostración del Pipeline CI/CD en Azure DevOps

El archivo de configuración [azure-pipelines.yml](file:///c:/Users/PC%20RST/Desktop/Proyectos%20Antigravity/futbolito%207/azure-pipelines.yml) contiene 3 etapas:
1. **SecurityAndLinting:** Flake8 (sintaxis), Bandit (análisis SAST ISO 27034) y pip-audit (vulnerabilidades SCA).
2. **TestAndBuild (CI):** Compilación de integridad y ejecución automatizada de la suite de pruebas unitarias (`python manage.py test`).
3. **DeployProduction (CD):** Empaquetado del artefacto `.zip` para Azure App Service (solo si los tests pasan en verde).

---

### Paso a Paso para la Demostración del Pipeline

#### CASO 1: Mostrar el Pipeline FALLANDO (Rojo 🔴)
Para demostrar al docente que el pipeline realmente valida la calidad y detiene despliegues defectuosos:

1. Abrir el archivo `apps/canchas/tests.py`.
2. En la línea 52, cambiar intencionalmente la aserción para que falle:
   ```python
   # Cambiar:
   self.assertEqual(self.tarifa_valle.tipo_horario, Tarifa.TipoHorario.VALLE)
   # Por un error forzado:
   self.assertEqual(self.tarifa_valle.tipo_horario, "ERROR_FORZADO_DEMO")
   ```
3. Guardar, hacer commit y push a la rama en Azure Repos:
   ```bash
   git add apps/canchas/tests.py
   git commit -m "test(demo): forzar fallo intencional para demostracion docente"
   git push origin develop  # o main
   ```
4. **En la pantalla de Azure Pipelines:**
   - La Etapa 1 (DevSecOps) pasa.
   - La Etapa 2 (**TestAndBuild**) se detiene en **ROJO** con código de error 1.
   - El docente verá en el log de Azure Pipelines el desglose exacto:
     `FAILED (failures=1) ... AssertionError: 'VALLE' != 'ERROR_FORZADO_DEMO'`.
   - La Etapa 3 (**DeployProduction**) se **cancela automáticamente**, protegiendo el entorno productivo.

---

#### CASO 2: Mostrar el Pipeline PASANDO EN VERDE (Verde 🟢)
1. Restaurar la aserción correcta en `apps/canchas/tests.py`:
   ```python
   self.assertEqual(self.tarifa_valle.tipo_horario, Tarifa.TipoHorario.VALLE)
   ```
2. Ejecutar localmente para verificar:
   ```bash
   .\.venv\Scripts\python.exe manage.py test
   # Resultado: Ran 10 tests in 0.084s - OK
   ```
3. Hacer commit y push:
   ```bash
   git add apps/canchas/tests.py
   git commit -m "fix(demo): corregir prueba unitaria y pasar CI en verde"
   git push origin main
   ```
4. **En la pantalla de Azure Pipelines:**
   - **Etapa 1 (DevSecOps):** Flake8 (0 errores), Bandit (0 vulnerabilidades SAST), pip-audit (OK) ✅.
   - **Etapa 2 (Test & Build):** 10/10 tests unitarios y de concurrencia pesimista aprobados ✅.
   - **Etapa 3 (Deploy & Package):** Empaquetado exitoso del artefacto `futbolito7-app.zip` listo para Azure App Service ✅.
