# INFORME DE DESCUBRIMIENTO DE NEGOCIO: INFORMACIÓN CRÍTICA Y MODELO OPERATIVO
**Proyecto:** Futbolito 7 — Plataforma Web de Gestión y Reservas de Canchas Deportivas  
**Destinatario:** Equipo de Proyecto & Docente de Cátedra  
**Objetivo:** Identificar, estructurar y analizar la información crítica para el cliente (dueños y administradores de complejos deportivos) y su modelo de negocio, justificando el valor de la solución tecnológica.

---

## 1. Resumen Ejecutivo
Para que un software de gestión deportiva sea exitoso, no basta con automatizar una agenda; debe responder directamente a la viabilidad económica y operatividad del cliente. 

El cliente de **Futbolito 7** es el **dueño o administrador de complejos de canchas de fútbol amateur**. Su negocio se basa en la venta de un activo altamente perecible: **el tiempo de cancha**. Una hora que no se arrienda a las 20:00 hrs es un inventario que se pierde para siempre y no genera ingresos retroactivos.

Este informe desglosa la economía real de los complejos deportivos, los datos críticos que el dueño necesita para no perder dinero y cómo la plataforma transforma esa información en rentabilidad y control.

---

## 2. Radiografía del Modelo de Negocio del Cliente

### 2.1 Fuentes de Ingreso (Revenue Streams)
1. **Arriendo Principal por Bloque Horario (80% - 85% de los ingresos totales):**
   - Cobro por bloques cerrados de 60 minutos.
   - Tarificación diferenciada de mercado en Chile:
     * *Horario Valle (09:00 a 17:00 hrs):* \$22.000 a \$28.000 CLP / hora.
     * *Horario Punta (18:00 a 23:00 hrs y fines de semana):* \$36.000 a \$45.000 CLP / hora.
2. **Ingresos Complementarios / Tercer Tiempo (15% - 20%):**
   - Venta de bebidas, isotónicas y snacks en quiosco/cafetería posterior al partido.
   - Arriendo de indumentaria deportiva (petos, balones oficiales) o implementos de arquero.
   - Escuelas de fútbol infantil o academias en horarios diurnos muertos.
   - Organización de ligas o torneos corporativos de fin de semana.

### 2.2 Estructura de Costos del Complejo (Cost Structure)
* **Costos Fijos Operativos:**
  - Arriendo del terreno / canon de concesión municipal o privada (el costo más pesado).
  - Remuneraciones del personal de recepción, administración y guardias.
  - Servicios básicos de alto consumo (energía eléctrica para focos halógenos/LED de alta potencia y agua para camarines).
* **Costos Variables y de Mantenimiento:**
  - Mantenimiento periódico del pasto sintético (cepillado, reposición de caucho granulado, mantención de costuras).
  - Reposición de mallas perimetrales y redes de arcos.
  - Comisiones financieras por uso de POS / pasarelas de pago (1.5% a 2.9% + IVA).

---

## 3. Información y Datos Críticos para el Negocio (Lo que el Cliente DEBE saber)

A continuación se detallan las variables de información que determinan el éxito o quiebra de un complejo deportivo:

### 3.1 La Métrica Clave: Tasa de Ocupación por Franja Horaria
* **El Problema:** La mayoría de los complejos llenan el horario punta (19:00 a 23:00) al 95%, pero en horario diurno (09:00 a 17:00) la ocupación cae a un crítico **15% - 25%**.
* **Información Crítica Requerida:** 
  - Mapa de calor (*Heatmap*) de ocupación por día de la semana y por cancha específica (ej. Techada vs. Descubierta).
  - Cálculo automático del **RevPAH** (*Revenue Per Available Hour* o Ingreso por Hora Disponible): mide cuánto dinero genera cada cancha en cada hora potencial de operación.

### 3.2 Tasa de Cancelación Tardía y "No-Show" (Partidos Fantasma)
* **El Problema:** Cuando un grupo cancela 30 minutos antes o simplemente no llega, el complejo sufre una **pérdida irrecuperable de \$38.000**. Esa cancha ya no se puede colocar en el mercado con tan poco margen.
* **Información Crítica Requerida:**
  - Historial de confiabilidad y cancelaciones del cliente (registro de morosidad o faltas).
  - Tiempo promedio de anticipación con el que se liberan los cupos.
  - Porcentaje de ingresos protegidos mediante prepago o seña obligatoria.

### 3.3 Conciliación de Medios de Pago y Prevención de Fugas de Caja
* **El Problema:** Al gestionar reservas por WhatsApp, los clientes envían comprobantes de transferencia bancaria que suelen ser:
  - Comprobantes falsificados con edición de imagen.
  - Transferencias realizadas a cuentas personales no consolidadas.
  - Pagos parciales donde la mitad del equipo se va sin pagar su cuota presencial.
* **Información Crítica Requerida:**
  - Cuadratura exacta de caja en tiempo real: Desglose de ingresos por Pasarela en Línea, Transferencias validadas y Efectivo recaudado en mostrador.
  - Registro de auditoría (*Audit Trail*) de cobros manuales: Saber qué operador de recepción autorizó el ingreso de una cancha y bajo qué medio de pago.

### 3.4 Dependencia Climática y Factor de Contingencia
* **El Problema:** En días de lluvia o viento extremo, las canchas descubiertas sufren un 100% de anulación, mientras que las canchas techadas se saturan de demanda.
* **Información Crítica Requerida:**
  - Capacidad de bloqueo preventivo por contingencia y reprogramación ágil de saldos a favor (crédito en plataforma) para evitar la devolución de dinero líquido.

---

## 4. Matriz de Valor: ¿Cómo Futbolito 7 responde a esta Información Crítica?

| Información Crítica del Cliente | Impacto en su Negocio | Solución Diseñada en Futbolito 7 |
|---|---|---|
| **Ocupación Ociosa en Horario Valle** | Pérdida de hasta el 40% del potencial de facturación mensual. | **Tarifas Diferenciadas Automáticas:** Precios promocionales diurnos (\$26.000) visibles en calendario HTMX para atraer universitarios y trabajadores con horario flexible. |
| **Pérdidas por No-Show** | Bloques reservados que quedan vacíos sin cobro. | **Prepago Obligatorio / Split Payment:** La reserva solo se confirma si se paga el total o los cupos 6v6 antes de un tiempo límite, protegiendo el 100% del ingreso. |
| **Falta de Jugadores (Cancelaciones)** | Los partidos se caen porque "faltaron 2 jugadores". | **Matchmaking 6v6:** Salas públicas que permiten a jugadores individuales sumarse y completar el arriendo, salvando el partido y la facturación de la cancha. |
| **Descuadre y Fugas en Recepción** | Desconfianza entre el dueño y los empleados de turno por dinero en efectivo. | **Panel de Turnos & Check-in QR con Auditoría:** Toda reserva llega pagada o con cobro presencial registrado con firma digital del operador en `AuditLog`. |
| **Ceguera Financiera del Dueño** | El administrador no sabe qué cancha es más rentable ni a qué hora subir precios. | **Dashboard de Métricas con Agregaciones ORM:** Gráficos en tiempo real de ingresos brutos, ocupación por cancha y horas con sobredemanda. |

---

## 5. Conclusión y Recomendación Estratégica
La información más crítica para el cliente no es técnica, sino **financiera y operativa**:
1. **Reducir a cero el riesgo de horas vacías no cobradas.**
2. **Eliminar el costo administrativo del cobro informal manual.**
3. **Optimizar el rendimiento por metro cuadrado de cada cancha.**

Al plantear el proyecto desde esta perspectiva, **Futbolito 7 deja de ser una simple "agenda digital" y se convierte en un motor de rentabilidad y gobernanza de negocio para el dueño del complejo**.
