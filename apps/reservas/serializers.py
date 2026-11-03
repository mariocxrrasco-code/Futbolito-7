from rest_framework import serializers
from apps.reservas.models import BloqueHorario, Reserva
from apps.canchas.serializers import CanchaSerializer


class BloqueHorarioSerializer(serializers.ModelSerializer):
    cancha = CanchaSerializer(read_only=True)
    cancha_id = serializers.IntegerField(source="cancha.id", read_only=True)
    hora_inicio_str = serializers.SerializerMethodField()
    hora_fin_str = serializers.SerializerMethodField()
    esta_disponible = serializers.SerializerMethodField()
    dentro_ventana_temporal = serializers.SerializerMethodField()
    mensaje_ventana = serializers.SerializerMethodField()

    class Meta:
        model = BloqueHorario
        fields = [
            "id", "cancha_id", "cancha", "fecha", "hora_inicio", "hora_fin",
            "hora_inicio_str", "hora_fin_str", "precio", "es_punta",
            "estado", "esta_disponible", "dentro_ventana_temporal", "mensaje_ventana"
        ]

    def get_hora_inicio_str(self, obj) -> str:
        return obj.hora_inicio.strftime("%H:%M")

    def get_hora_fin_str(self, obj) -> str:
        return obj.hora_fin.strftime("%H:%M")

    def get_esta_disponible(self, obj) -> bool:
        return obj.esta_disponible()

    def get_dentro_ventana_temporal(self, obj) -> bool:
        valido, _ = obj.validar_ventana_temporal()
        return valido

    def get_mensaje_ventana(self, obj) -> str:
        _, msg = obj.validar_ventana_temporal()
        return msg


class ReservaCreateInputSerializer(serializers.Serializer):
    bloque_id = serializers.IntegerField(required=True)
    rut_cliente = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    nombre_cliente = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    telefono_cliente = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    email_cliente = serializers.EmailField(required=False, allow_blank=True, default="")
    notas = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ReservaDetailSerializer(serializers.ModelSerializer):
    bloque = BloqueHorarioSerializer(read_only=True)
    email_enmascarado = serializers.ReadOnlyField()
    telefono_enmascarado = serializers.ReadOnlyField()
    estado_reserva_display = serializers.CharField(source="get_estado_reserva_display", read_only=True)
    gestionado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = [
            "id", "codigo", "bloque", "rut_cliente", "nombre_cliente",
            "telefono_enmascarado", "email_enmascarado",
            "tipo_reserva", "estado_reserva", "estado_reserva_display",
            "estado_pago", "monto_total", "expiracion_bloqueo", "notas",
            "gestionado_por_nombre", "fecha_gestion", "motivo_decision", "creado_en"
        ]

    def get_gestionado_por_nombre(self, obj) -> str:
        if obj.gestionado_por:
            return obj.gestionado_por.get_full_name() or obj.gestionado_por.username
        return ""
