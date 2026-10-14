# GUÍA DE ESTUDIO Y DEFENSA: MEJORA ISO 27034 (MATRIZ DE RIESGOS) + HERRAMIENTA CI/CD (AZURE PIPELINES)
**Proyecto:** Futbolito 7  
**Equipo Scrum:** Eliezer Zenteno, Mario Carrasco, Paulo Alegría, Iván Alejandro

---

## PARTE A: LA MEJORA EN LA ISO 27034 (LA MATRIZ DE RIESGOS Y CÓMO SE RIGE)

A partir de la retroalimentación del profesor en la Parte I, incorporamos una **Matriz de Evaluación y Priorización de Riesgos** formal para no elegir los controles de seguridad al azar, sino justificar matemáticamente **cuál se programa primero y por qué**.

### 1. ¿Bajo qué normas y criterios se rige nuestra Matriz?
Nuestra matriz se rige por la combinación de **3 marcos internacionales**:
1. **ISO/IEC 27005:** Norma oficial para la Gestión de Riesgos de Seguridad de la Información.
2. **OWASP Risk Rating Methodology:** Metodología estándar para estimar la probabilidad técnica de una amenaza web y su impacto en el negocio.
3. **ISO/IEC 27034-1 + MoSCoW:** Para traducir el puntaje de riesgo en el orden de implementación de los Controles de Seguridad de la Aplicación (ASC).

### 2. ¿Cómo funciona la fórmula y las escalas?
Calculamos el **RPN (Risk Priority Number / Puntaje de Riesgo)** multiplicando dos factores:

$$\text{RPN} = \text{Probabilidad (1 al 5)} \times \text{Impacto al Cliente (1 al 10)} \quad [\text{Rango: 1 a 50 puntos}]$$

* **Escala de Probabilidad (1 al 5):** Qué tan probable es que ocurra en una cancha real (1 = Muy Baja, 3 = Media, 5 = Muy Alta/Inminente en horas punta).
* **Escala de Impacto hacia el Cliente (1 al 10):** Mide el daño real para el jugador (B2C), la empresa en convenio (B2B) y el dueño del complejo:
  * **1 – 2 (Insignificante):** Molestia visual leve; el partido se juega igual.
  * **3 – 4 (Bajo):** Fricción menor (ej. repetir un Captcha); no se pierde la reserva.
  * **5 – 6 (Medio):** Retraso administrativo o reprogramación de cancha con devolución.
  * **7 – 8 (Crítico):** Pérdida económica directa ($38.000 por cancha) y jugadores en recepción sin cancha (*no-show* forzado).
  * **9 – 10 (Catastrófico):** Fraude financiero masivo, quiebra de caja o demandas legales por Ley 19.628 (filtración de RUTs/correos o ruptura de contratos B2B).

### 3. Resultado de la Matriz (El orden obligatorio de programación)
| Orden | ID | Riesgo | Probabilidad (1-5) | Impacto (1-10) | RPN (1-50) | Prioridad |
|:---:|:---:|---|:---:|:---:|:---:|---|
| **1°** | **R-01** | **Overbooking (Colisión concurrente)** | 5 | 10 | **50** | Crítica (Se hace 1°) |
| **2°** | **R-04** | **Comprobantes de pago falsos** | 4 | 9 | **36** | Crítica (Se hace 2°) |
| **3°** | **R-05** | **Fuga de datos personales (PII)** | 3 | 9 | **27** | Crítica (Se hace 3°) |
| **4°** | **R-02** | **Bots acaparando canchas sin pagar** | 3 | 8 | **24** | Alta (Se hace 4°) |
| **5°** | **R-03** | **Parálisis por poner todas las canchas en mantención** | 2 | 8 | **16** | Alta (Se hace 5°) |

---

## PARTE B: LA HERRAMIENTA CI/CD (AZURE PIPELINES — SELECCIÓN, INSTALACIÓN Y USO REAL)

### ¿Cómo funciona de punta a punta lo que instalamos?
1. **Repositorio fuente:** Conectamos el repositorio Git (`mariocxrrasco-code/Futbolito-7`) que contiene en su raíz el archivo declarativo `azure-pipelines.yml` y `requirements.txt`.
2. **Disparadores (Triggers):** Se activa automáticamente con cada `commit` o `Pull Request` hacia las ramas `main` y `develop`.
3. **Agente de ejecución:** Usa el pool administrado por Microsoft `vmImage: 'ubuntu-latest'` con **Python 3.12**.
4. **Flujo de 3 Etapas (Stages) ejecutado en 2m 16s (Corrida `#20261009.1`):**
   * **Etapa 1 (`SecurityAndLinting` - 43s):** Instala herramientas y corre `flake8` (errores de sintaxis), `bandit` (SAST para auditar código seguro según ISO 27034) y `pip-audit` (SCA para buscar vulnerabilidades CVEs en las librerías).
   * **Etapa 2 (`TestAndBuild` - 35s):** Solo arranca si la Etapa 1 pasó en verde (`condition: succeeded()`). Instala todas las dependencias de Django 6.1 (`requirements.txt`) y ejecuta `python -m compileall .` para validar la integridad y compilación de todos los módulos Python.
   * **Etapa 3 (`DeployProduction` - 15s):** Solo arranca si la Etapa 2 pasó en verde y estamos en la rama `main`. Usa la tarea `ArchiveFiles@2` para comprimir el proyecto en `futbolito7-app-$(Build.BuildId).zip` y `PublishBuildArtifacts@1` para dejar publicado el paquete (`drop`) listo para Azure App Service.
5. **Trazabilidad en Azure Boards:** El build `#20261009.1` quedó enlazado en la sección *Development* de la **Task 99 ("Pipeline de pruebas automáticas en Azure Pipelines")** con estado `Done`.

---

## PARTE C: REPARTO EXACTO PARA LOS 4 INTEGRANTES EN LA DEFENSA

### 👤 1. ELIEZER ZENTENO (Por qué la Matriz de Riesgos + Selección de Azure Pipelines)
1. **Sobre la mejora ISO 27034 (Gobernanza de la Matriz):**
   * *"Siguiendo su retroalimentación, agregamos en el Lineamiento 5 una Matriz de Riesgos regida por **ISO/IEC 27005** y **OWASP Risk Rating**. Definimos una escala de Impacto al Cliente del 1 al 10 que distingue entre clientes naturales (B2C) y convenios de empresas (B2B), donde un impacto 7-8 es dejar a 12 jugadores sin cancha en recepción, y un 9-10 es fraude financiero o multa legal por Ley 19.628."*
2. **Sobre la selección de la herramienta CI/CD:**
   * *"Seleccionamos **Azure Pipelines** por sobre Jenkins o GitHub Actions por tres razones: primero, la **cohesión nativa** con nuestro tablero en Azure Boards y la Wiki; segundo, la **trazabilidad directa** entre Work Items, commits y builds; y tercero, la gobernanza de **Pipeline como Código** mediante el archivo `azure-pipelines.yml` versionado en la raíz."*

---

### 👤 2. MARIO CARRASCO (Instalación desde Cero, Conexión Git y Trazabilidad en Boards)
1. **Sobre la instalación y aprovisionamiento real del Pipeline:**
   * *"Al principio tuvimos un bloqueo con la plantilla por defecto porque intentaba ejecutar una matriz de Python 3.8 a 3.11 sin `requirements.txt` y arrojaba error de trigger `TF401019`. Para solucionarlo, aprovisionamos el pipeline desde cero: preparamos el repositorio en GitHub (`mariocxrrasco-code/Futbolito-7`) con el `requirements.txt` oficial del stack y nuestro `azure-pipelines.yml` personalizado."*
   * *"En Azure DevOps fuimos a **Pipelines > New pipeline**, autorizamos la integración con GitHub mediante la App de Azure Pipelines, vinculamos el archivo YAML existente y aprovisionamos un agente limpio `ubuntu-latest` con Python 3.12."*
2. **Sobre la ejecución en verde y cierre en Azure Boards:**
   * *"Ejecutamos la corrida `#20261009.1` logrando los 3 stages en verde en **2 minutos y 16 segundos**, y cerramos el ciclo de trazabilidad vinculando esa ejecución directamente en la **Task 99** de nuestro Sprint en Azure Boards."*

---

### 👤 3. PAULO ALEGRÍA (Cálculo del RPN en la Matriz + Etapa 1 DevSecOps del Pipeline)
1. **Sobre la fórmula RPN y el orden de prioridad en la Matriz:**
   * *"Para decidir qué control programar primero en la ISO 27034, aplicamos la fórmula $\text{RPN} = \text{Probabilidad (1 a 5)} \times \text{Impacto (1 a 10)}$ (rango de 1 a 50). Eso nos dio un orden estricto: 1° el Overbooking (`R-01`) con 50 puntos, 2° el fraude de comprobantes (`R-04`) con 36 puntos, y 3° la fuga de datos PII (`R-05`) con 27 puntos."*
2. **Sobre la Etapa 1 del Pipeline (`SecurityAndLinting`):**
   * *"Yo estructuré la **Etapa 1 de DevSecOps** en el YAML (que tardó 43 segundos en ejecutarse). Esta etapa conecta la norma ISO 27034 con el pipeline ejecutando tres herramientas automatizadas en cada commit:*
     * *`flake8`: verifica que no existan errores de sintaxis en Python 3.12.*
     * *`bandit`: realiza Análisis Estático de Seguridad (SAST) buscando malas prácticas o vulnerabilidades en el código.*
     * *`pip-audit`: realiza Análisis de Composición de Software (SCA) escaneando todas las librerías de `requirements.txt` contra la base de datos de vulnerabilidades CVEs."*

---

### 👤 4. IVÁN ALEJANDRO (Etapas 2 y 3 del Pipeline: CI, Base de Datos y Empaquetado CD)
1. **Sobre la Etapa 2 de Integración Continua (`TestAndBuild`):**
   * *"La **Etapa 2 (CI)** tiene la condición `dependsOn: SecurityAndLinting` y `condition: succeeded()`, por lo que solo se ejecuta si la auditoría de seguridad de la Etapa 1 fue aprobada. En 35 segundos configura Python 3.12, instala el stack real de producción (`Django`, `djangorestframework`, `psycopg[binary]`, `Pillow`, `gunicorn`) y ejecuta `python -m compileall .` para verificar la integridad de todos los módulos antes de permitir cualquier merge. Además, dejamos definida la arquitectura con contenedor de servicio `postgres:16-alpine` para las pruebas transaccionales de concurrencia (`select_for_update`)."*
2. **Sobre la Etapa 3 de Entrega Continua (`DeployProduction`):**
   * *"La **Etapa 3 (CD)** está protegida con la condición de que solo corre si los tests pasaron y la rama es `main`. En 15 segundos utiliza la tarea `ArchiveFiles@2` para empaquetar todo el código validado en un archivo `.zip` con el ID del build (`futbolito7-app-$(Build.BuildId).zip`) y usa `PublishBuildArtifacts@1` para publicar el artefacto `drop`, dejándolo listo para el despliegue en Azure App Service."*
