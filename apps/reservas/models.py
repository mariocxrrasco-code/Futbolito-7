import uuid
import datetime
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from apps.canchas.models import Cancha


class PerfilUsuario(models.Model):
    class Rol(models.TextChoices):
        CLIENTE = "CLIENTE", "Cliente / Jugador"
        ADMIN = "ADMIN", "Administrador del Complejo"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
        verbose_name="Usuario"
    )
    rol = models.CharField(
        max_length=15,
        choices=Rol.choices,
        default=Rol.CLIENTE,
        verbose_name="Rol de Cuenta"
    )
    rut = models.CharField(max_length=20, blank=True, default="", verbose_name="RUT")
    telefono = models.CharField(max_length=30, blank=True, default="", verbose_name="Teléfono Móvil")
    cuenta_validada = models.BooleanField(default=True, verbose_name="Cuenta Validada por Correo")
    token_validacion = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    suspendido = models.BooleanField(default=False, verbose_name="Suspendido por Admin")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} ({self.get_rol_display()})"

    @property
    def es_admin(self) -> bool:
        return self.rol == self.Rol.ADMIN or self.usuario.is_staff or self.usuario.is_superuser


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
        rango = f"{self.hora_inicio.strftime('%H:%M')}-{self.hora_fin.strftime('%H:%M')}"
        return f"{self.cancha.nombre} | {self.fecha.strftime('%d/%m/%Y')} {rango} [{self.get_estado_display()}]"

    def esta_disponible(self) -> bool:
        """
        Retorna True si el bloque está disponible o si su bloqueo temporal de 10 min ya expiró,
        y además no tiene una reserva EN_ESPERA o ACEPTADA activa.
        """
        if self.cancha.estado != 'OPERATIVA' or not self.cancha.activa:
            return False
        if self.estado == self.Estado.DISPONIBLE:
            return True
        if self.estado == self.Estado.EN_PROCESO_PAGO and self.expiracion_bloqueo:
            if self.reservas.filter(estado_reserva='EN_ESPERA').exists():
                return False
            return timezone.now() > self.expiracion_bloqueo
        return False

    def validar_ventana_temporal(self, ahora=None) -> tuple[bool, str]:
        """
        PUNTO 3 DEL PROFESOR: Límite temporal coherente para reservar.
        - Mínimo 60 minutos (1 hora) de anticipación antes del inicio del turno.
        - Máximo 14 días de anticipación (no permite reservar con meses de antelación).
        """
        if ahora is None:
            ahora = timezone.now()
        tz = timezone.get_current_timezone()
        inicio_naive = datetime.datetime.combine(self.fecha, self.hora_inicio)
        inicio_aware = timezone.make_aware(inicio_naive, tz) if timezone.is_naive(inicio_naive) else inicio_naive

        diferencia = inicio_aware - ahora
        if diferencia < datetime.timedelta(minutes=60):
            return False, "No se puede reservar con menos de 60 minutos de anticipación ni en horarios pasados."

        dias_anticipacion = (self.fecha - timezone.localdate(ahora)).days
        if dias_anticipacion > 14:
            return False, "No se puede reservar con más de 14 días de anticipación."

        return True, "OK"

    @property
    def reserva(self):
        return self.reservas.exclude(estado_reserva="DENEGADA").first()


class Reserva(models.Model):
    class EstadoReserva(models.TextChoices):
        EN_ESPERA = "EN_ESPERA", "En Espera de Aprobación"
        ACEPTADA = "ACEPTADA", "Aceptada por Administración"
        DENEGADA = "DENEGADA", "Denegada por Administración"

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
    bloque = models.ForeignKey(
        BloqueHorario,
        on_delete=models.PROTECT,
        related_name="reservas",
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
    estado_reserva = models.CharField(
        max_length=20,
        choices=EstadoReserva.choices,
        default=EstadoReserva.EN_ESPERA,
        verbose_name="Estado de la Reserva"
    )
    rut_cliente = models.CharField(max_length=20, blank=True, default="", verbose_name="RUT del Cliente")
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
    gestionado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_gestionadas",
        verbose_name="Administrador que Gestionó"
    )
    fecha_gestion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Decisión Admin"
    )
    motivo_decision = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Observación del Administrador"
    )
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
