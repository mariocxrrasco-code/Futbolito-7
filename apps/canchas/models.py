from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class Complejo(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Complejo")
    direccion = models.CharField(max_length=255, verbose_name="Dirección")
    comuna = models.CharField(max_length=100, default="Santiago", verbose_name="Comuna")
    telefono = models.CharField(max_length=30, blank=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, verbose_name="Correo Electrónico")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    class Meta:
        verbose_name = "Complejo Deportivo"
        verbose_name_plural = "Complejos Deportivos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.comuna})"


class Superficie(models.Model):
    nombre = models.CharField(max_length=80, unique=True, verbose_name="Tipo de Superficie")
    descripcion = models.TextField(blank=True, verbose_name="Descripción Técnica")

    class Meta:
        verbose_name = "Superficie"
        verbose_name_plural = "Superficies"

    def __str__(self):
        return self.nombre


class Cancha(models.Model):
    ESTADOS = (
        ('OPERATIVA', 'Operativa'),
        ('MANTENCION', 'En Mantención'),
        ('INACTIVA', 'Inactiva'),
    )

    complejo = models.ForeignKey(
        Complejo,
        on_delete=models.CASCADE,
        related_name="canchas",
        verbose_name="Complejo"
    )
    nombre = models.CharField(max_length=100, verbose_name="Nombre o Número de Cancha")
    medidas = models.CharField(
        max_length=60,
        default="50m x 30m (Fútbol 7 Reglamentario)",
        verbose_name="Medidas de la Cancha"
    )
    superficie = models.ForeignKey(
        Superficie,
        on_delete=models.PROTECT,
        related_name="canchas",
        verbose_name="Superficie"
    )
    techada = models.BooleanField(default=False, verbose_name="¿Es Techada?")
    iluminacion_led = models.BooleanField(default=True, verbose_name="Iluminación LED")
    precio_base = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(0)],
        verbose_name="Precio Base (CLP)"
    )
    descuento_valle = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(0)],
        verbose_name="Descuento Horario Diurno (%)"
    )
    foto = models.ImageField(upload_to="canchas/", blank=True, null=True, verbose_name="Fotografía")
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='OPERATIVA',
        verbose_name="Estado Operativo"
    )
    activa = models.BooleanField(default=True, verbose_name="Disponible para Reserva")
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canchas_modificadas",
        verbose_name="Última modificación por"
    )
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")

    class Meta:
        verbose_name = "Cancha"
        verbose_name_plural = "Canchas"
        ordering = ["complejo", "nombre"]
        unique_together = ("complejo", "nombre")

    def __str__(self):
        return f"{self.nombre} - {self.complejo.nombre}"

    def calcular_precio_bloque(self, es_punta: bool) -> int:
        """
        Retorna el precio del bloque en CLP:
        - Horario normal/punta (es_punta=True): 100% del precio_base editable por el Admin.
        - Horario diurno/valle (es_punta=False): aplica el % de descuento configurado (por defecto 20%).
        """
        base = int(self.precio_base)
        dcto = max(0, min(int(self.descuento_valle or 0), 90))
        if es_punta or dcto == 0:
            return base
        return int(round(base * (100 - dcto) / 100.0))

    @property
    def precio_con_descuento(self) -> int:
        return self.calcular_precio_bloque(es_punta=False)

    def clean(self):
        """
        CONTROL R-03 (ISO 27034): Regla estricta de continuidad del servicio.
        Impide que el complejo supere el 40% de canchas en mantención o inactivas simultáneamente.
        """
        super().clean()
        if self.complejo_id and self.estado in ['MANTENCION', 'INACTIVA']:
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
                        f"El complejo quedaría con un {porcentaje_fuera:.1f}% fuera "
                        f"de servicio (Máximo permitido: 40%)."
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Tarifa(models.Model):
    class TipoHorario(models.TextChoices):
        VALLE = "VALLE", "Horario Valle (Diurno Promo)"
        PUNTA = "PUNTA", "Horario Punta (Nocturno / Fin de Semana)"

    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.CASCADE,
        related_name="tarifas",
        verbose_name="Cancha"
    )
    tipo_horario = models.CharField(
        max_length=10,
        choices=TipoHorario.choices,
        default=TipoHorario.VALLE,
        verbose_name="Tipo de Franja"
    )
    dia_semana = models.IntegerField(
        choices=[
            (0, "Lunes"), (1, "Martes"), (2, "Miércoles"),
            (3, "Jueves"), (4, "Viernes"), (5, "Sábado"), (6, "Domingo")
        ],
        verbose_name="Día de la Semana"
    )
    hora_inicio = models.TimeField(verbose_name="Hora Inicio")
    hora_fin = models.TimeField(verbose_name="Hora Fin")
    precio_bloque = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        validators=[MinValueValidator(0)],
        verbose_name="Precio del Bloque (CLP)"
    )

    class Meta:
        verbose_name = "Tarifa Horaria"
        verbose_name_plural = "Tarifas Horarias"
        ordering = ["cancha", "dia_semana", "hora_inicio"]

    def __str__(self):
        rango = f"{self.hora_inicio.strftime('%H:%M')}-{self.hora_fin.strftime('%H:%M')}"
        return f"{self.cancha.nombre} | {self.get_dia_semana_display()} {rango} (${self.precio_bloque:,.0f} CLP)"


class HistorialModificacionCancha(models.Model):
    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.CASCADE,
        related_name="historial_modificaciones",
        verbose_name="Cancha"
    )
    administrador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="registro_ediciones_cancha",
        verbose_name="Administrador Responsable"
    )
    detalle_cambio = models.CharField(max_length=255, verbose_name="Detalle de la Modificación")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    class Meta:
        verbose_name = "Historial de Modificación de Cancha"
        verbose_name_plural = "Historial de Modificaciones de Canchas"
        ordering = ["-fecha"]

    def __str__(self):
        if self.administrador:
            admin_str = self.administrador.get_full_name() or self.administrador.username
        else:
            admin_str = "Sistema"
        return f"{self.cancha.nombre} modificado por {admin_str} ({self.fecha.strftime('%d/%m/%Y %H:%M')})"

    @property
    def admin_usuario(self):
        return self.administrador

    @property
    def resumen_cambios(self):
        return self.detalle_cambio
