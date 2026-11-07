from rest_framework import serializers
from apps.canchas.models import Complejo, Superficie, Cancha


class SuperficieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Superficie
        fields = ["id", "nombre", "descripcion"]


class CanchaSerializer(serializers.ModelSerializer):
    superficie = SuperficieSerializer(read_only=True)
    complejo_nombre = serializers.ReadOnlyField(source="complejo.nombre")
    modificado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Cancha
        fields = [
            "id", "nombre", "medidas", "complejo", "complejo_nombre",
            "superficie", "techada", "iluminacion_led",
            "precio_base", "descuento_valle", "precio_con_descuento",
            "estado", "activa", "modificado_por_nombre",
            "fecha_modificacion"
        ]

    def get_modificado_por_nombre(self, obj) -> str:
        if obj.modificado_por:
            return obj.modificado_por.get_full_name() or obj.modificado_por.username
        return "Configuración Inicial"


class ComplejoSerializer(serializers.ModelSerializer):
    canchas = CanchaSerializer(many=True, read_only=True)

    class Meta:
        model = Complejo
        fields = ["id", "nombre", "direccion", "comuna", "telefono", "email", "activo", "canchas"]
