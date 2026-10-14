# WIKI AZURE DEVOPS — EVALUACIÓN 2 (PARTE II)
## SELECCIÓN, INSTALACIÓN Y USO REAL DE LA HERRAMIENTA CI/CD
**Proyecto:** Futbolito 7 — Plataforma Web de Gestión y Reservas de Complejos Deportivos  
**Herramienta Seleccionada:** **Azure Pipelines** (Ecosistema Azure DevOps Services)  
**Organización:** `https://dev.azure.com/eliezerzenteno/Futbolito%207`  
**Entrega:** Sábado, 10 de Octubre de 2026  
**Autores:** Equipo Scrum Futbolito 7 (Eliezer Zenteno, Mario Carrasco, Paulo Alegría, Iván Alejandro)  

---

## 1. Selección y Justificación de la Herramienta CI/CD

Para el proyecto **Futbolito 7**, se seleccionó **Azure Pipelines** como motor de Integración Continua (CI) y Entrega Continua (CD).

### 1.1 ¿Por qué Azure Pipelines sobre GitHub Actions o Jenkins?
1. **Cohesión Nativa con Azure DevOps:** Nuestro proyecto ya gestiona sus historias y tareas en **Azure Boards**, aloja el código fuente bajo Git en **Azure Repos** y documenta la arquitectura en **Azure DevOps Wiki**. Azure Pipelines se integra de forma directa sin requerir plugins externos ni puentes de autenticación de terceros.
2. **Trazabilidad Total (Work Item Linking):** Cada ejecución del pipeline se vincula automáticamente con los *Commits*, *Pull Requests* y los *Work Items* de Azure Boards (Issues y Tasks), permitiendo al docente y al Product Owner (Eliezer Zenteno) auditar qué tarea disparó qué despliegue.
3. **Soporte Multiplataforma para el Stack Tecnológico:** Soporta agentes nativos de Linux (`ubuntu-latest`) con Python 3.12, contenedores de servicio para **PostgreSQL 16**, herramientas de análisis de seguridad (**Bandit**, **pip-audit**) y empaquetado para despliegue en **Azure App Service**.
4. **Pipelines como Código (As-Code Governance):** La configuración se define mediante un archivo declarativo versionado `azure-pipelines.yml`, garantizando reproducibilidad y control de cambios bajo auditoría ISO 27034.

---

### 1.2 Características Principales de Azure Pipelines

| Característica | Detalle Técnico | Beneficio Directo en Futbolito 7 |
|---|---|---|
| **Definición YAML Declarativa** | Archivo `azure-pipelines.yml` en la raíz del repositorio. | Control de versiones, ramas protegidas y revisiones de código mediante Pull Requests. |
| **Service Containers (Contenedores de Servicio)** | Capacidad de levantar servicios auxiliares efímeros en Docker durante el build. | Permite levantar una instancia real de **PostgreSQL 16** durante el job de CI para ejecutar pruebas de concurrencia (`select_for_update`) con transacciones reales. |
| **Security Gates & DevSecOps** | Tareas de validación estática (SAST) y análisis de dependencias (SCA) integradas al build. | Bloquea la integración a la rama `main` si `bandit` detecta vulnerabilidades críticas o si `pip-audit` encuentra CVEs conocidas. |
| **Secret Management (Variables Seguras)** | Grupos de variables encriptadas en *Azure DevOps Library* con enlace a *Azure Key Vault*. | Desacopla credenciales críticas (`DATABASE_URL`, `SECRET_KEY`, `WEBPAY_API_KEY`) del código fuente, cumpliendo con la metodología Doce Factores. |
| **Estrategia de Ambientes y Aprobación** | Separación entre etapas de *Build & Test*, *Staging* y *Production*. | El Product Owner (Eliezer) o Scrum Master (Mario) deben aprobar manualmente la promoción a producción antes del despliegue en Azure App Service. |

---

## 2. Documentación de Instalación y Aprovisionamiento

Azure Pipelines opera en la nube pero requiere una configuración paso a paso dentro de la organización y el repositorio. A continuación se documenta el aprovisionamiento real realizado por el equipo:

### Paso 1: Habilitación de Pipelines y Conexión con Repositorio Git (GitHub / Azure Repos)
1. Acceder a la organización oficial de Azure DevOps: `https://dev.azure.com/eliezerzenteno/Futbolito%207`.
2. En el menú de navegación lateral izquierdo, seleccionar la sección **Pipelines** > **Pipelines**.
3. Hacer clic en el botón superior derecho **New pipeline**.
4. En el asistente interactivo *Where is your code?*, seleccionar el proveedor Git correspondiente (**GitHub** o **Azure Repos Git**).
5. Seleccionar el repositorio oficial del proyecto: `mariocxrrasco-code/Futbolito-7` (o `Futbolito 7`).
6. En la pantalla *Configure your pipeline*, seleccionar **Existing Azure Pipelines YAML file** apuntando a `/azure-pipelines.yml`.

---

### Paso 2: Selección y Aprovisionamiento del Agente de Ejecución (Pool de Agentes)
Para garantizar builds limpios, reproducibles e independientes del sistema operativo local de los desarrolladores:
* **Pool Seleccionado:** **Azure Pipelines Hosted Pool** (`vmImage: 'ubuntu-latest'`).
* **Justificación:** Los agentes administrados por Microsoft vienen preconfigurados con Docker, Git, Python y utilitarios de red, garantizando que el entorno de pruebas sea idéntico en cada ejecución sin arrastrar residuos temporales de builds anteriores.

---

### Paso 3: Configuración del Grupo de Variables Seguras y Parámetros
Para no exponer credenciales ni claves de cifrado en el repositorio Git (cumplimiento ISO 27034):
1. Configurar variables de entorno y parámetros de ejecución:
   - `pythonVersion`: `3.12`.
   - `DJANGO_SECRET_KEY`: Llave criptográfica de producción.
   - `DEBUG`: `False`.
   - `DB_NAME`: `futbolito7_test_db`.
   - `DB_USER`: `postgres`.
   - `DB_PASSWORD`: `PostgresSecurePass2026!`.
   - `DB_HOST`: `localhost`.
   - `DB_PORT`: `5432`.
4. Otorgar permisos de acceso al pipeline en la pestaña *Pipeline permissions*.

---

### Paso 4: Políticas de Rama (Branch Policies) para la rama `main`
Para asegurar que ningún código se integre sin pasar el pipeline exitosamente:
1. Ir a **Repos** > **Branches**.
2. En los tres puntos (...) de la rama `main`, seleccionar **Branch policies**.
3. En la sección **Build validation**, hacer clic en **+ Add build validation**.
4. Seleccionar el pipeline de `Futbolito 7`, fijar el disparador como *Automatic* y el requerimiento como *Required*.
5. **Resultado:** Ningún integrante (Mario, Paulo, Iván, Eliezer) puede hacer `git push` directo a `main`; todo cambio debe pasar por Pull Request y aprobar el 100% de los tests del pipeline.

---

## 3. Uso Real de Azure Pipelines en el Desarrollo de Futbolito 7

El pipeline no es una maqueta: está diseñado para ejecutar un flujo de 3 etapas (*Stages*) adaptado a nuestro stack de **Django 6.1 + PostgreSQL 16 + HTMX + DevSecOps**:

```
                                  FLUJO REAL DEL PIPELINE DE CI/CD
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|  [ PULL REQUEST / COMMIT ] ---> TRIGGER: main & develop                                                 |
|                                                                                                         |
|  +---------------------------------------------------------------------------------------------------+  |
|  | ETAPA 1: DEVSECOPS & CALIDAD (SAST + SCA + LINTING)                                                |  |
|  |  * Flake8: Verificación de estilo PEP 8 y sintaxis Python 3.12                                    |  |
|  |  * Bandit: Análisis estático de código seguro (SAST - Criterio ISO 27034)                           |  |
|  |  * pip-audit: Escaneo de vulnerabilidades conocidas (CVEs) en requirements.txt                    |  |
|  +---------------------------------------------------------------------------------------------------+  |
|                                                  |                                                      |
|                                                  v (Aprobado)                                           |
|  +---------------------------------------------------------------------------------------------------+  |
|  | ETAPA 2: INTEGRACIÓN CONTINUA (CI CON POSTGRESQL 16 EFÍMERO)                                      |  |
|  |  * Levantar Contenedor Docker: postgres:16-alpine                                                  |  |
|  |  * Ejecutar migraciones nativas: python manage.py migrate                                          |  |
|  |  * Ejecutar suite de pruebas: python manage.py test (Tests de concurrencia y select_for_update)   |  |
|  |  * Publicar resultados de pruebas y cobertura de código                                            |  |
|  +---------------------------------------------------------------------------------------------------+  |
|                                                  |                                                      |
|                                                  v (Aprobado en rama main)                              |
|  +---------------------------------------------------------------------------------------------------+  |
|  | ETAPA 3: ENTREGA Y DESPLIEGUE CONTINUO (CD A AZURE APP SERVICE)                                    |  |
|  |  * Empaquetado de artefacto (.zip de aplicación Django)                                            |  |
|  |  * Despliegue automatizado en Azure App Service (Linux Web App)                                    |  |
|  |  * Notificación automática a Azure Boards                                                          |  |
|  +---------------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------------+
```

---

### 3.1 Archivo Declarativo Oficial: `azure-pipelines.yml`
Este es el archivo YAML real que se incorpora en la raíz del repositorio Git:

```yaml
name: $(Date:yyyyMMdd)$(Rev:.r)-futbolito7-ci-cd

# Disparadores: Cada commit o Pull Request en main y develop activa el pipeline
trigger:
  branches:
    include:
      - main
      - develop

pr:
  branches:
    include:
      - main

pool:
  vmImage: 'ubuntu-latest'

# Variables globales y enlace al grupo de secretos
variables:
  - group: futbolito7-secrets
  - name: pythonVersion
    value: '3.12'

stages:
  # =========================================================================
  # ETAPA 1: VALIDACIÓN DE CALIDAD Y SEGURIDAD DEVSECOPS (ISO 27034)
  # =========================================================================
  - stage: SecurityAndLinting
    displayName: '1. Calidad de Código y DevSecOps (SAST & SCA)'
    jobs:
      - job: CodeAudit
        displayName: 'Auditoría de Código y Dependencias'
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: $(pythonVersion)
            displayName: 'Configurar entorno Python $(pythonVersion)'

          - script: |
              python -m pip install --upgrade pip
              pip install flake8 bandit pip-audit
              pip install -r requirements.txt
            displayName: 'Instalar herramientas de análisis de seguridad'

          # Linting de estilo
          - script: |
              flake8 apps/ config/ --count --select=E9,F63,F7,F82 --show-source --statistics
            displayName: 'Verificación sintáctica con Flake8'

          # Análisis Estático de Código Seguro (SAST - Criterio 9 ISO 27034)
          - script: |
              bandit -r apps/ config/ -ll -ii
            displayName: 'Escaneo SAST contra vulnerabilidades con Bandit'

          # Auditoría de dependencias conocidas (SCA)
          - script: |
              pip-audit -r requirements.txt
            displayName: 'Escaneo de vulnerabilidades CVEs con pip-audit'

  # =========================================================================
  # ETAPA 2: PRUEBAS AUTOMATIZADAS CON BASE DE DATOS POSTGRESQL 16 REAL
  # =========================================================================
  - stage: TestAndBuild
    displayName: '2. Pruebas Unitarias e Integración (CI)'
    dependsOn: SecurityAndLinting
    condition: succeeded()
    jobs:
      - job: DjangoTests
        displayName: 'Ejecución de Pruebas Unitarias y de Concurrencia'
        # Levanta un contenedor PostgreSQL 16 idéntico al motor de producción
        services:
          postgres: postgres_service
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: $(pythonVersion)
            displayName: 'Configurar Python $(pythonVersion)'

          - script: |
              python -m pip install --upgrade pip
              pip install -r requirements.txt
            displayName: 'Instalar dependencias de Futbolito 7'

          - script: |
              python manage.py check
              python manage.py migrate --noinput
            displayName: 'Ejecutar migraciones en PostgreSQL'
            env:
              DATABASE_URL: postgres://$(DB_USER):$(DB_PASSWORD)@localhost:5432/$(DB_NAME)
              SECRET_KEY: $(DJANGO_SECRET_KEY)
              DEBUG: 'False'

          # Ejecuta la suite de pruebas unitarias y de concurrencia pesimista
          - script: |
              python manage.py test apps/ --verbosity 2
            displayName: 'Ejecutar suite de tests Django'
            env:
              DATABASE_URL: postgres://$(DB_USER):$(DB_PASSWORD)@localhost:5432/$(DB_NAME)
              SECRET_KEY: $(DJANGO_SECRET_KEY)
              DEBUG: 'False'

          # Publica los resultados de pruebas para visualización del docente en Azure
          - task: PublishTestResults@2
            condition: succeededOrFailed()
            inputs:
              testResultsFormat: 'JUnit'
              testResultsFiles: '**/test-*.xml'
              testRunTitle: 'Resultados de Pruebas Unitarias Futbolito 7'
            displayName: 'Publicar Reporte de Pruebas en Azure Pipelines'

  # =========================================================================
  # ETAPA 3: DESPLIEGUE CONTINUO EN AZURE APP SERVICE (CD)
  # =========================================================================
  - stage: DeployProduction
    displayName: '3. Despliegue Continuo (CD)'
    dependsOn: TestAndBuild
    # Solo se ejecuta si los tests pasaron exitosamente y el commit está en main
    condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
    jobs:
      - deployment: DeployAppService
        displayName: 'Despliegue a Azure App Service'
        environment: 'production'
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureWebApp@1
                  inputs:
                    azureSubscription: 'Azure-Subscription-Futbolito7'
                    appType: 'webAppLinux'
                    appName: 'futbolito7-app'
                    package: '$(Pipeline.Workspace)/**/*.zip'
                    runtimeStack: 'PYTHON|3.12'
                    startUpCommand: 'gunicorn config.wsgi:application --bind 0.0.0.0:8000'
                  displayName: 'Desplegar aplicación Django en Azure Web App'

# Definición del contenedor de servicio PostgreSQL 16
resources:
  containers:
    - container: postgres_service
      image: postgres:16-alpine
      ports:
        - 5432:5432
      env:
        POSTGRES_USER: $(DB_USER)
        POSTGRES_PASSWORD: $(DB_PASSWORD)
        POSTGRES_DB: $(DB_NAME)
```

---

## 4. Evidencias de Uso Real y Trazabilidad en el Desarrollo

Para demostrar el **uso real** durante el desarrollo de Futbolito 7:

1. **Protección de la Integridad en Pull Requests:**
   - Cuando Paulo Alegría o Mario Carrasco crean un Pull Request desde una rama de característica (ej. `feature/canchas-crud`), Azure Pipelines dispara automáticamente el job `SecurityAndLinting`. Si algún desarrollador introdujo un error de sintaxis o una librería vulnerable en `requirements.txt`, el build se marca en rojo con ❌ y el botón de *Merge* queda bloqueado.
2. **Validación de Concurrencia (`select_for_update`) en CI:**
   - Gracias al contenedor de servicio `postgres:16-alpine`, las pruebas de estrés concurrente escritas en `apps/reservas/tests.py` se ejecutan contra un motor PostgreSQL real (no SQLite), garantizando que las transacciones atómicas funcionen antes de subir a producción.
3. **Visibilidad en Azure Boards y Trazabilidad:**
   - Cada ejecución del pipeline informa su estado de *Success* o *Failed* en el panel de despliegues del Work Item asociado, cerrando el ciclo de trazabilidad exigido en la pauta: **Requerimiento &rarr; Tarea &rarr; Código &rarr; Pipeline CI/CD**.
4. **Ejecución Real Verificada en Azure Pipelines (Evidencia de Aprobación):**
   - **Ejecución:** `#20261009.1 - futbolito7-ci-cd` ejecutada por **Mario Alejandro Carrasco Calderón**.
   - **Tiempo de ejecución:** 2m 16s en agente `ubuntu-latest`.
   - **Resultado por Etapas:**
     - `1. Calidad de Código y DevSecOps (SAST & SCA)`: **Aprobado ✅** (43s) - Flake8, Bandit y pip-audit ejecutados.
     - `2. Pruebas Automatizadas e Integración (CI)`: **Aprobado ✅** (35s) - Entorno Python 3.12 y compilación verificados.
     - `3. Empaquetado y Entrega Continua (CD)`: **Aprobado ✅** (15s) - Artefacto .ZIP generado y publicado (`drop`).
