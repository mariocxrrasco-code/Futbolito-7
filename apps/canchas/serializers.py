from rest_framework import serializers
from apps.canchas.models import Complejo, Superficie, Cancha, Tarifa


class SuperficieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Superficie
        fields = ["id", "nombre", "descripcion"]


class CanchaSerializer(serializers.ModelSerializer):
    superficie = SuperficieSerializer(read_only=True)
    complejo_nombre = serializers.ReadOnlyField(source="complejo.nombre")

    class Meta:
        model = Cancha
        fields = [
            "id", "nombre", "complejo", "complejo_nombre",
            "superficie", "techada", "iluminacion_led",
            "precio_base", "estado", "activa"
        ]


class ComplejoSerializer(serializers.ModelSerializer):
    canchas = CanchaSerializer(many=True, read_only=True)

    class Meta:
        model = Complejo
        fields = ["id", "nombre", "direccion", "comuna", "telefono", "email", "activo", "canchas"]
