from django.contrib import admin
from apps.canchas.models import Complejo, Superficie, Cancha, Tarifa


@admin.register(Complejo)
class ComplejoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "comuna", "telefono", "email", "activo", "creado_en")
    list_filter = ("activo", "comuna")
    search_fields = ("nombre", "direccion", "comuna")


@admin.register(Superficie)
class SuperficieAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")
    search_fields = ("nombre",)


class TarifaInline(admin.TabularInline):
    model = Tarifa
    extra = 1


@admin.register(Cancha)
class CanchaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "complejo", "superficie", "estado", "techada", "iluminacion_led", "precio_base", "activa")
    list_filter = ("estado", "complejo", "superficie", "techada", "activa")
    search_fields = ("nombre", "complejo__nombre")
    inlines = [TarifaInline]


@admin.register(Tarifa)
class TarifaAdmin(admin.ModelAdmin):
    list_display = ("cancha", "tipo_horario", "dia_semana", "hora_inicio", "hora_fin", "precio_bloque")
    list_filter = ("tipo_horario", "dia_semana", "cancha__complejo")
    search_fields = ("cancha__nombre",)
