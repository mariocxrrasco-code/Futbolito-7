# WIKI AZURE DEVOPS — EVALUACIÓN 2 (PARTE I PERFECCIONADA)
## GOBERNANZA DE SEGURIDAD EN APLICACIONES (ISO/IEC 27034)
**Proyecto:** Futbolito 7 — Plataforma Web de Gestión y Reservas de Complejos Deportivos  
**Organización:** `https://dev.azure.com/eliezerzenteno/Futbolito%207` | **Fecha:** Octubre 2026  
**Autores:** Equipo Scrum Futbolito 7 (Eliezer Zenteno, Mario Carrasco, Paulo Alegría, Iván Alejandro)  

---

```
                              ARQUITECTURA DE SEGURIDAD MULTICAPA (ISO/IEC 27034)

+---------------------------------------------------------------------------------------------------------------+
| 1. CAPA FRONTEND (UI/UX - HTMX / Alpine.js / Tailwind CSS)                                                    |
|    * Rate Limiting visual & Captcha en Checkout            * CSRF Tokens forzosos en peticiones HTMX          |
|    * Temporizador regresivo 10 min de bloqueo              * Feedback inmediato ante error HTTP 409 Conflict  |
+---------------------------------------------------------------------------------------------------------------+
                                                       | HTTP / JSON / Form Data
                                                       v
+---------------------------------------------------------------------------------------------------------------+
| 2. CAPA BACKEND (Django 6.1 + DRF 3.18)                                                                       |
|    * Rutina transaccional atómica (transaction.atomic)     * Validación Módulo 11 en RUTs B2C y B2B           |
|    * Webhook HMAC Signature para Pasarelas de Pago         * Middleware de Ofuscación PII (AuditLogMiddleware)|
|    * Validación de continuidad operacional (clean method)  * RBAC estricto en decoradores / permissions       |
+---------------------------------------------------------------------------------------------------------------+
                                                       | ORM / Psycopg 3.3
                                                       v
+---------------------------------------------------------------------------------------------------------------+
| 3. CAPA BASE DE DATOS (PostgreSQL 16)                                                                         |
|    * Bloqueo pesimista de fila: SELECT ... FOR UPDATE      * CHECK Constraints (Regla máx 40% mantención)     |
|    * Nivel de aislamiento: READ COMMITTED con transacciones * Tablas inmutables para bitácora forense         |
+---------------------------------------------------------------------------------------------------------------+
                                                       | Criptografía / Reposo
                                                       v
+---------------------------------------------------------------------------------------------------------------+
| 4. CAPA DE INTEGRIDAD Y CRIPTOGRAFÍA (Hashing & Tokens)                                                       |
|    * Passwords: Argon2 / PBKDF2-SHA256                     * Enmascaramiento irreversible de RUT/Email en logs|
|    * Tokens de sesión con HttpOnly, SameSite=Strict, Secure* Firma digital QR con HMAC-SHA256                 |
+---------------------------------------------------------------------------------------------------------------+
```

---

## 1. Lineamiento 4: Identificación de Requisitos de Seguridad

### 1.1 Contexto y Actores del Negocio: Matriz de Validación Jurídica
El modelo de negocio de Futbolito 7 distingue dos perfiles de consumo con requisitos de validación jurídica y niveles de riesgo diferenciados:

* **Cliente Común / Persona Natural (B2C):**
  - **Identificación:** Cédula de Identidad (RUT chileno con algoritmo Módulo 11), Nombre, Correo y Móvil.
  - **Capacidad de Reserva:** Máximo 2 bloques horarios simultáneos o por día para neutralizar ataques de denegación de inventario (*Inventory Exhaustion Attack*).
  - **Tributación:** Emisión automática de Boleta Electrónica de Servicios vía SII / API de facturación.
* **Empresas / Convenios Corporativos (B2B):**
  - **Identificación:** Validación de RUT Empresa, Razón Social, Giro Comercial acreditado, poder de representación legal y contacto administrativo del Club Deportivo Laboral.
  - **Capacidad de Reserva:** Lotes de bloques recurrentes mensuales o arriendos exclusivos para torneos corporativos, bajo contrato formal con aprobación del Administrador.
  - **Tributación:** Emisión obligatoria de Factura Electrónica Afecta o Exenta de IVA.

### 1.2 Regla de Continuidad Operacional y Capacidad del Servicio
El inventario de un complejo deportivo comercial es estrictamente perecible: una hora no vendida es pérdida irrecuperable.
* **Inventario Total Protegido:** Complejo estándar de 4 canchas (2 techadas, 2 aire libre) en franja de 14 horas diarias (09:00 a 23:00 hrs) = **56 bloques horarios diarios de capacidad máxima**.
* **Regla Anti-Parálisis Operacional:** Está estrictamente prohibido que el 100% de las canchas estén en estado `MANTENCION` o `INACTIVA`. La capacidad operativa no puede descender del **60% en días hábiles** ni del **75% en fines de semana**. Cualquier cambio en el admin que vulnere este umbral es abortado con `ValidationError` y código HTTP 400.
* **Tiempo de Amortiguación (Buffer Time):** Ventana de 10 minutos de limpieza y desalojo entre bloques para mitigar incidentes físicos en cancha.

### 1.3 Clasificación Tripartita de Información
1. **Datos Públicos:** Catálogo de canchas, fotografías, superficie, iluminación y grilla de disponibilidad.
2. **Meta-Información de Capacidad:** Índices de ocupación en tiempo real, tasas de conversión horaria, umbrales de sobrecarga y estados del inventario (`DISPONIBLE`, `EN_PROCESO_PAGO`, `RESERVADO`, `MANTENCION`).
3. **Datos Sensibles y Privados (PII):** RUT, números telefónicos, correos, tokens de pago Webpay/Stripe y bitácora de auditoría.

---

## 2. Lineamiento 5: Evaluación y Gestión de Riesgos

### 2.1 Metodología de Evaluación y Escala de Impacto al Cliente (1 al 10)
> **Origen del Criterio:** Basado en la **Metodología de Clasificación de Riesgos de OWASP (Risk Rating Methodology)** y en la norma **ISO/IEC 27005 (Gestión de Riesgos de Seguridad de la Información)**.

Se adopta una **escala de Impacto hacia el Cliente del 1 al 10** ponderada según el daño financiero, operacional y legal:

| Nivel de Impacto | Calificación (1 - 10) | Definición Operacional y Daño al Cliente | Variación por Actor de Negocio |
|---|:---:|---|---|
| **Insignificante** | **1 – 2** | Molestia visual leve; sin pérdida económica ni interrupción del partido. | **B2C / B2B:** Demora cosmética en carga de estilos. |
| **Bajo** | **3 – 4** | Fricción menor; reintento de reserva exitoso sin degradación de inventario. | **B2C:** Reingreso de captcha; **B2B:** Validación manual adicional. |
| **Medio** | **5 – 6** | Retraso administrativo o anulación a tiempo con devolución íntegra. | **B2C:** Reprogramación de cancha; **B2B:** Ajuste de factura mensual. |
| **Crítico** | **7 – 8** | Pérdida económica directa; clientes que llegan a jugar y no tienen cancha disponible (*no-show* forzado). | **B2C:** Furia de 12 jugadores en recepción; **Dueño:** Pérdida de $38.000. |
| **Catastrófico** | **9 – 10** | Fraude financiero sistemático, quiebra del modelo de arriendos o sanciones regulatorias por Ley 19.628 / GDPR por fuga masiva de PII. | **Dueño:** Quiebra de caja, demandas legales de empresas B2B y daño reputacional irrecuperable. |

---

### 2.2 Tabla Maestra de Priorización y Orden de Implementación (¿Cuál va primero y por qué?)
> **Criterio de Ordenamiento:**  
> $$\text{Puntaje de Riesgo (RPN)} = \text{Probabilidad (1 a 5)} \times \text{Impacto Cliente (1 a 10)} \quad [\text{Rango 1 a 50}]$$  
> **Origen Metodológico:** Priorización de Controles de Seguridad de Aplicaciones (ASC) bajo la norma **ISO/IEC 27034-1** complementada con el marco ágil **MoSCoW**.

| Orden | ID | Amenaza / Escenario de Riesgo | Probabilidad (1-5) | Impacto Cliente (1-10) | Severidad RPN (1-50) | Nivel de Prioridad | Capas Afectadas |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| **1°** | **R-01** | **Colisión Concurrente (Overbooking):** Dos usuarios reservan y pagan la misma cancha simultáneamente. | 5 (Muy Alta) | **10 (Catastrófico)** | **50** | **Prioridad 1 (Crítica)** | Base de Datos, Backend, Frontend |
| **2°** | **R-04** | **Suplantación de Comprobantes de Pago:** Clientes envían capturas bancarias falsas para liberar turnos. | 4 (Alta) | **9 (Catastrófico)** | **36** | **Prioridad 1 (Crítica)** | Backend, Criptografía, Integración |
| **3°** | **R-05** | **Fuga o Exposición de PII:** Filtración de RUT, teléfonos y correos en endpoints de Matchmaking o reportes. | 3 (Media) | **9 (Catastrófico)** | **27** | **Prioridad 1 (Crítica)** | Backend, Base de Datos, Criptografía |
| **4°** | **R-02** | **Agotamiento Malicioso de Inventario:** Bots bloquean canchas sin pagar, vaciando el inventario disponible. | 3 (Media) | **8 (Crítico)** | **24** | **Prioridad 2 (Alta)** | Frontend, Backend (Rate Limit) |
| **5°** | **R-03** | **Parálisis por Configuración Errónea:** El staff marca por error todas las canchas en mantención simultánea. | 2 (Baja) | **8 (Crítico)** | **16** | **Prioridad 2 (Alta)** | Base de Datos, Backend (Model Clean) |

---

## 3. Lineamiento 6: Controles de Seguridad Implementativos (Código Fuente Real)

---

### 🛡️ Implementación R-01 (1° Prioridad): Anti-Overbooking Concurrente Pesimista
* **Capas Involucradas:** Base de Datos (PostgreSQL 16) + Backend (Django Service Layer) + Frontend (HTMX).
* **Ubicación del Código:** `apps/reservas/services.py`
* **Implementación Real:**

```python
# apps/reservas/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from .models import BloqueHorario, Reserva

class ReservaService:
    @staticmethod
    def bloquear_bloque_concurrente(bloque_id: int, usuario, tipo_reserva: str) -> Reserva:
        """
        CONTROL R-01 (ISO 27034): Bloqueo pesimista de fila en PostgreSQL 16.
        Garantiza aislamiento ACID contra carreras críticas (Race Conditions).
        """
        with transaction.atomic():
            # CAPA BD: SELECT ... FOR UPDATE bloquea la fila a nivel de motor SQL
            try:
                bloque = (
                    BloqueHorario.objects
                    .select_for_update(nowait=False)
                    .get(id=bloque_id, estado='DISPONIBLE')
                )
            except BloqueHorario.DoesNotExist:
                raise ValidationError(
                    "El bloque horario seleccionado ya fue tomado o se encuentra en proceso de pago.",
                    code='bloque_ocupado'
                )

            # CAPA BACKEND: Cambia estado temporal y define expiración a 10 minutos
            bloque.estado = 'EN_PROCESO_PAGO'
            bloque.save(update_fields=['estado'])

            nueva_reserva = Reserva.objects.create(
                bloque=bloque,
                usuario=usuario,
                tipo_reserva=tipo_reserva,
                estado_pago='PENDIENTE',
                expiracion_bloqueo=timezone.now() + timedelta(minutes=10)
            )
            return nueva_reserva
```

---

### 🛡️ Implementación R-04 (2° Prioridad): Verificación Criptográfica de Pagos (Anti-Fraude)
* **Capas Involucradas:** Criptografía (HMAC-SHA256) + Backend (Webhook Seguro) + Integración Webpay.
* **Ubicación del Código:** `apps/pagos/webhooks.py`
* **Implementación Real:**

```python
# apps/pagos/webhooks.py
import hmac
import hashlib
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from .models import Pago

@csrf_exempt
def webhook_confirmacion_pasarela(request):
    """
    CONTROL R-04 (ISO 27034): Verificación de firma criptográfica HMAC en Webhook.
    Elimina la recepción informal de comprobantes falsificados.
    """
    firma_recibida = request.headers.get('X-Signature-SHA256')
    if not firma_recibida:
        return HttpResponseForbidden("Firma criptográfica ausente.")

    # CAPA CRIPTOGRÁFICA: Comparación segura de tiempo constante para evitar Timing Attacks
    firma_esperada = hmac.new(
        key=settings.PASARELA_SECRET_KEY.encode('utf-8'),
        msg=request.body,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(firma_recibida, firma_esperada):
        return HttpResponseForbidden("Firma digital inválida: transacción rechazada.")

    # CAPA BACKEND: Confirmar pago legítimo y actualizar reserva
    token_transaccion = request.POST.get('token')
    Pago.objects.confirmar_pago_legitimo(token_transaccion)
    return JsonResponse({"status": "PAGO_CONFIRMADO"})
```

---

### 🛡️ Implementación R-05 (3° Prioridad): Middleware de Ofuscación y Anonimización PII
* **Capas Involucradas:** Backend (Middleware Django) + Base de Datos (`AuditLog`) + Criptografía de Hashing.
* **Ubicación del Código:** `apps/auditoria/middleware.py`
* **Implementación Real:**

```python
# apps/auditoria/middleware.py
import re
from .models import AuditLog

class AuditLogPIIMiddleware:
    """
    CONTROL R-05 (ISO 27034): Interceptor de eventos sensibles.
    Enmascara obligatoriamente RUTs, teléfonos y correos antes de persistir en AuditLog.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in ['POST', 'PUT', 'DELETE'] and response.status_code < 400:
            self.registrar_auditoria_segura(request)
        return response

    @staticmethod
    def enmascarar_pii(texto: str) -> str:
        # Enmascara RUT: 18.456.789-K -> 18.***.***-K
        texto = re.sub(r'(\d{1,2})\.\d{3}\.\d{3}-([\dkK])', r'\1.***.***-\2', texto)
        # Enmascara Email: mario.carrasco@gmail.com -> m***o@gmail.com
        texto = re.sub(r'(\b[A-Za-z])[A-Za-z0-9._%+-]+([A-Za-z])@', r'\1***\2@', texto)
        return texto

    def registrar_auditoria_segura(self, request):
        AuditLog.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            ip_origen=request.META.get('REMOTE_ADDR'),
            accion=f"{request.method} {request.path}",
            payload_seguro=self.enmascarar_pii(request.body.decode('utf-8', errors='ignore'))
        )
```

---

### 🛡️ Implementación R-02 (4° Prioridad): Rate Limiting y Control de Agotamiento de Inventario
* **Capas Involucradas:** Frontend (Alpine.js / Captcha) + Backend (Django Ratelimit & Validadores).
* **Ubicación del Código:** `apps/reservas/views.py`
* **Implementación Real:**

```python
# apps/reservas/views.py
from django_ratelimit.decorators import ratelimit
from django.shortcuts import render
from django.http import HttpResponseForbidden
from .models import Reserva

# CAPA BACKEND: Máximo 3 intentos de reserva por minuto por IP
@ratelimit(key='ip', rate='3/m', block=True)
def checkout_reserva_view(request, bloque_id):
    """
    CONTROL R-02 (ISO 27034): Mitigación contra Inventory Hoarding y Bots.
    """
    # Restricción B2C: Máximo 2 reservas activas pendientes por persona
    if request.user.is_authenticated:
        reservas_activas = Reserva.objects.filter(
            usuario=request.user, 
            estado_pago='PENDIENTE'
        ).count()
        if reservas_activas >= 2:
            return HttpResponseForbidden("Has alcanzado el límite máximo de reservas simultáneas pendientes (2).")

    return render(request, "reservas/checkout.html", {"bloque_id": bloque_id})
```

---

### 🛡️ Implementación R-03 (5° Prioridad): Regla Estricta Anti-Parálisis Operacional
* **Capas Involucradas:** Backend (Método `clean()` en Django Model) + Base de Datos (CHECK Constraint).
* **Ubicación del Código:** `apps/canchas/models.py`
* **Implementación Real:**

```python
# apps/canchas/models.py
from django.db import models
from django.core.exceptions import ValidationError

class Cancha(models.Model):
    ESTADOS = (
        ('OPERATIVA', 'Operativa'),
        ('MANTENCION', 'En Mantención'),
        ('INACTIVA', 'Inactiva'),
    )
    complejo = models.ForeignKey('Complejo', on_delete=models.CASCADE, related_name='canchas')
    nombre = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='OPERATIVA')

    def clean(self):
        """
        CONTROL R-03 (ISO 27034): Regla estricta de continuidad del servicio.
        Impide que el complejo supere el 40% de canchas en mantención simultánea.
        """
        super().clean()
        if self.estado in ['MANTENCION', 'INACTIVA']:
            total_canchas = Cancha.objects.filter(complejo=self.complejo).count()
            if total_canchas > 0:
                canchas_fuera = (
                    Cancha.objects
                    .filter(complejo=self.complejo, estado__in=['MANTENCION', 'INACTIVA'])
                    .exclude(pk=self.pk)
                    .count() + 1
                )
                porcentaje_fuera = (canchas_fuera / total_canchas) * 100
                if porcentaje_fuera > 40.0:
                    raise ValidationError(
                        f"Infracción Operacional: No se puede deshabilitar la cancha. "
                        f"El complejo quedaría con un {porcentaje_fuera:.1f}% fuera de servicio (Máximo permitido: 40%)."
                    )
```

---

## 4. Lineamiento 9: Gestión de Vulnerabilidades y Ciclo de Vida

Para asegurar que los hallazgos no se queden en reportes estáticos, se vincula el proceso con **Azure Boards y Azure Pipelines**:

* **Escaneo Continuo de Librerías (SCA):** Integración de `pip-audit` y `safety` para validar automáticamente dependencias contra la base de datos de CVEs en cada commit.
* **Análisis Estático de Código Seguro (SAST):** Ejecución de `bandit` en el entorno local y en el pipeline para detectar uso de `assert` en producción, claves secretas hardcodeadas o inyecciones de comandos.
* **Matriz de Gestión y Tiempos de Respuesta (SLA) en Azure Boards:**
  - **Crítica (CVSS 9.0 - 10.0):** Rotura del build en Azure Pipelines; Hotfix prioritario antes de **24 horas** liderado por Paulo Alegría.
  - **Alta (CVSS 7.0 - 8.9):** Creación inmediata de Issue P1 en Azure Boards; corrección obligatoria antes del cierre del Sprint actual.
  - **Media / Baja (CVSS < 7.0):** Refinamiento e inclusión en el Backlog del siguiente Sprint.
