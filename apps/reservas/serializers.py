from rest_framework import serializers
from apps.reservas.models import BloqueHorario, Reserva
from apps.canchas.serializers import CanchaSerializer


class BloqueHorarioSerializer(serializers.ModelSerializer):
    cancha = CanchaSerializer(read_only=True)
    cancha_id = serializers.IntegerField(source="cancha.id", read_only=True)
    hora_inicio_str = serializers.SerializerMethodField()
    hora_fin_str = serializers.SerializerMethodField()
    esta_disponible = serializers.SerializerMethodField()

    class Meta:
        model = BloqueHorario
        fields = [
            "id", "cancha_id", "cancha", "fecha", "hora_inicio", "hora_fin",
            "hora_inicio_str", "hora_fin_str", "precio", "es_punta",
            "estado", "esta_disponible"
        ]

    def get_hora_inicio_str(self, obj) -> str:
        return obj.hora_inicio.strftime("%H:%M")

    def get_hora_fin_str(self, obj) -> str:
        return obj.hora_fin.strftime("%H:%M")

    def get_esta_disponible(self, obj) -> bool:
        return obj.esta_disponible()


class ReservaCreateInputSerializer(serializers.Serializer):
    bloque_id = serializers.IntegerField(required=True)
    nombre_cliente = serializers.CharField(max_length=150, required=True)
    telefono_cliente = serializers.CharField(max_length=30, required=True)
    email_cliente = serializers.EmailField(required=True)
    notas = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ReservaDetailSerializer(serializers.ModelSerializer):
    bloque = BloqueHorarioSerializer(read_only=True)
    email_enmascarado = serializers.ReadOnlyField()
    telefono_enmascarado = serializers.ReadOnlyField()

    class Meta:
        model = Reserva
        fields = [
            "id", "codigo", "bloque", "nombre_cliente",
            "telefono_enmascarado", "email_enmascarado",
            "tipo_reserva", "estado_pago", "monto_total",
            "expiracion_bloqueo", "notas", "creado_en"
        ]
