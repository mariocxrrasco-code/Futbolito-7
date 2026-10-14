from django.db import models
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
    foto = models.ImageField(upload_to="canchas/", blank=True, null=True, verbose_name="Fotografía")
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='OPERATIVA',
        verbose_name="Estado Operativo"
    )
    activa = models.BooleanField(default=True, verbose_name="Disponible para Reserva")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")

    class Meta:
        verbose_name = "Cancha"
        verbose_name_plural = "Canchas"
        ordering = ["complejo", "nombre"]
        unique_together = ("complejo", "nombre")

    def __str__(self):
        return f"{self.nombre} - {self.complejo.nombre}"

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
                        f"El complejo quedaría con un {porcentaje_fuera:.1f}% fuera de servicio (Máximo permitido: 40%)."
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
        return f"{self.cancha.nombre} | {self.get_dia_semana_display()} {self.hora_inicio.strftime('%H:%M')}-{self.hora_fin.strftime('%H:%M')} (${self.precio_bloque:,.0f} CLP)"
