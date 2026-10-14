from django.contrib import admin
from django.utils.html import format_html
from apps.reservas.models import BloqueHorario, Reserva


@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    list_display = ("cancha", "fecha", "rango_horario", "precio_formateado", "es_punta_badge", "estado_badge")
    list_filter = ("estado", "es_punta", "fecha", "cancha__complejo", "cancha")
    search_fields = ("cancha__nombre",)
    date_hierarchy = "fecha"

    @admin.display(description="Horario")
    def rango_horario(self, obj):
        return f"{obj.hora_inicio.strftime('%H:%M')} - {obj.hora_fin.strftime('%H:%M')}"

    @admin.display(description="Precio (CLP)")
    def precio_formateado(self, obj):
        return f"${obj.precio:,.0f} CLP"

    @admin.display(description="Tarifa")
    def es_punta_badge(self, obj):
        if obj.es_punta:
            return format_html('<span style="color: #ef4444; font-weight: bold;">⚡ Punta</span>')
        return format_html('<span style="color: #10b981; font-weight: bold;">🌱 Valle</span>')

    @admin.display(description="Disponibilidad")
    def estado_badge(self, obj):
        colores = {
            BloqueHorario.Estado.DISPONIBLE: "#10b981",
            BloqueHorario.Estado.EN_PROCESO_PAGO: "#f59e0b",
            BloqueHorario.Estado.RESERVADO: "#6b7280",
            BloqueHorario.Estado.MANTENCION: "#ef4444",
        }
        color = colores.get(obj.estado, "#000000")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_estado_display()
        )


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_corto",
        "bloque",
        "nombre_cliente",
        "telefono_privado",
        "email_privado",
        "monto_total_formateado",
        "estado_pago",
        "creado_en"
    )
    list_filter = ("estado_pago", "creado_en", "bloque__cancha__complejo")
    search_fields = ("codigo", "nombre_cliente", "telefono_cliente", "email_cliente")
    readonly_fields = ("codigo", "creado_en", "actualizado_en", "email_enmascarado", "telefono_enmascarado")

    @admin.display(description="Código")
    def codigo_corto(self, obj):
        return str(obj.codigo)[:8].upper()

    @admin.display(description="Teléfono (PII)")
    def telefono_privado(self, obj):
        return obj.telefono_enmascarado

    @admin.display(description="Email (PII)")
    def email_privado(self, obj):
        return obj.email_enmascarado

    @admin.display(description="Total")
    def monto_total_formateado(self, obj):
        return f"${obj.monto_total:,.0f} CLP"
