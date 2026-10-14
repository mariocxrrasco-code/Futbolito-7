import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from apps.canchas.models import Cancha


class BloqueHorario(models.Model):
    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        EN_PROCESO_PAGO = "EN_PROCESO_PAGO", "En Proceso de Pago"
        RESERVADO = "RESERVADO", "Reservado"
        MANTENCION = "MANTENCION", "En Mantención"

    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.CASCADE,
        related_name="bloques_horarios",
        verbose_name="Cancha"
    )
    fecha = models.DateField(verbose_name="Fecha")
    hora_inicio = models.TimeField(verbose_name="Hora Inicio")
    hora_fin = models.TimeField(verbose_name="Hora Fin")
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(0)],
        verbose_name="Precio del Bloque (CLP)"
    )
    es_punta = models.BooleanField(default=False, verbose_name="¿Es Horario Punta?")
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.DISPONIBLE,
        verbose_name="Estado de Disponibilidad"
    )
    expiracion_bloqueo = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expiración del Bloqueo Temporal (10 min)"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")

    class Meta:
        verbose_name = "Bloque Horario"
        verbose_name_plural = "Bloques Horarios"
        ordering = ["fecha", "hora_inicio", "cancha"]
        constraints = [
            models.UniqueConstraint(
                fields=["cancha", "fecha", "hora_inicio"],
                name="unique_cancha_fecha_hora"
            )
        ]
        indexes = [
            models.Index(fields=["fecha", "cancha", "estado"], name="idx_bloque_consulta"),
            models.Index(fields=["estado", "expiracion_bloqueo"], name="idx_bloque_expiracion"),
        ]

    def __str__(self):
        return f"{self.cancha.nombre} | {self.fecha.strftime('%d/%m/%Y')} {self.hora_inicio.strftime('%H:%M')}-{self.hora_fin.strftime('%H:%M')} [{self.get_estado_display()}]"

    def esta_disponible(self) -> bool:
        """
        Retorna True si el bloque está disponible o si su bloqueo temporal de 10 min ya expiró.
        """
        if self.estado == self.Estado.DISPONIBLE:
            return True
        if self.estado == self.Estado.EN_PROCESO_PAGO and self.expiracion_bloqueo:
            return timezone.now() > self.expiracion_bloqueo
        return False


class Reserva(models.Model):
    class EstadoPago(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de Pago"
        PAGADO = "PAGADO", "Pagado y Confirmado"
        CANCELADO = "CANCELADO", "Cancelado"

    class TipoReserva(models.TextChoices):
        B2C = "B2C", "Persona Natural (B2C)"
        B2B = "B2B", "Empresa / Convenio (B2B)"
        MATCHMAKING = "MATCHMAKING", "Matchmaking 6v6"

    codigo = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Código Único de Reserva"
    )
    bloque = models.OneToOneField(
        BloqueHorario,
        on_delete=models.PROTECT,
        related_name="reserva",
        verbose_name="Bloque Horario Asignado"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas",
        verbose_name="Usuario / Cliente"
    )
    tipo_reserva = models.CharField(
        max_length=20,
        choices=TipoReserva.choices,
        default=TipoReserva.B2C,
        verbose_name="Tipo de Reserva"
    )
    nombre_cliente = models.CharField(max_length=150, verbose_name="Nombre del Titular")
    telefono_cliente = models.CharField(max_length=30, verbose_name="Teléfono Celular")
    email_cliente = models.EmailField(verbose_name="Correo Electrónico")
    estado_pago = models.CharField(
        max_length=20,
        choices=EstadoPago.choices,
        default=EstadoPago.PENDIENTE,
        verbose_name="Estado del Pago"
    )
    monto_total = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(0)],
        verbose_name="Monto Total Pagado (CLP)"
    )
    expiracion_bloqueo = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expiración del Bloqueo Temporal (10 min)"
    )
    notas = models.TextField(blank=True, verbose_name="Notas u Observaciones")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Reserva #{str(self.codigo)[:8]} - {self.nombre_cliente} ({self.bloque.cancha.nombre})"

    # =========================================================================
    # AUDITORÍA Y PRIVACIDAD PII (ISO 27034 / Protección de Datos Personales)
    # =========================================================================
    @property
    def email_enmascarado(self) -> str:
        """Enmascara el correo para visualización segura: j***n@correo.cl"""
        if not self.email_cliente or "@" not in self.email_cliente:
            return "***"
        usuario, dominio = self.email_cliente.split("@", 1)
        if len(usuario) <= 2:
            usuario_mask = usuario[0] + "***"
        else:
            usuario_mask = usuario[0] + "***" + usuario[-1]
        return f"{usuario_mask}@{dominio}"

    @property
    def telefono_enmascarado(self) -> str:
        """Enmascara el teléfono para visualización segura: +56 9 **** 1234"""
        tel = self.telefono_cliente.strip()
        if len(tel) <= 4:
            return "****"
        return f"{tel[:4]} **** {tel[-4:]}"
