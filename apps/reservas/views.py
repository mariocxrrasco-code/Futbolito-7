import datetime
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.canchas.models import Cancha, Complejo
from apps.reservas.models import BloqueHorario, Reserva
from apps.reservas.serializers import (
    BloqueHorarioSerializer,
    ReservaCreateInputSerializer,
    ReservaDetailSerializer
)
from apps.reservas.services import ConcurrenciaService, ReservaConflictError


class GrillaReservasView(TemplateView):
    """
    Vista principal de la grilla interactiva de reservas para Futbolito 7.
    """
    template_name = "canchas/grilla.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        fecha_str = self.request.GET.get("fecha", hoy.isoformat())
        try:
            fecha_sel = datetime.date.fromisoformat(fecha_str)
        except ValueError:
            fecha_sel = hoy

        canchas = Cancha.objects.filter(activa=True).select_related("superficie", "complejo")
        complejo = Complejo.objects.filter(activo=True).first()

        context.update({
            "complejo": complejo,
            "canchas": canchas,
            "fecha_seleccionada": fecha_sel.isoformat(),
            "hoy": hoy.isoformat(),
            "fecha_display": fecha_sel.strftime("%A, %d de %B de %Y").capitalize(),
        })
        return context


class ApiDisponibilidadView(APIView):
    """
    Endpoint JSON para obtener la disponibilidad de bloques horarios por fecha.
    Soporta filtro por `fecha` (YYYY-MM-DD).
    """
    def get(self, request):
        fecha_str = request.query_params.get("fecha")
        if not fecha_str:
            fecha = timezone.localdate()
        else:
            try:
                fecha = datetime.date.fromisoformat(fecha_str)
            except ValueError:
                return Response(
                    {"error": "Formato de fecha inválido. Utilice YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        bloques = BloqueHorario.objects.filter(fecha=fecha).select_related(
            "cancha", "cancha__superficie", "cancha__complejo"
        ).order_by("hora_inicio", "cancha__nombre")

        serializer = BloqueHorarioSerializer(bloques, many=True)
        return Response({
            "fecha": fecha.isoformat(),
            "total_bloques": bloques.count(),
            "bloques": serializer.data
        })


class ApiReservarBloqueView(APIView):
    """
    Endpoint JSON para reservar un bloque con control de concurrencia pesimista (select_for_update).
    Regla R-01 (ISO 27034): Cero sobreventa en transacciones simultáneas.
    """
    def post(self, request):
        input_serializer = ReservaCreateInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                {"error": "Datos inválidos", "detalles": input_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = input_serializer.validated_data
        try:
            reserva = ConcurrenciaService.reservar_bloque_pesimista(
                bloque_id=data["bloque_id"],
                nombre_cliente=data["nombre_cliente"],
                telefono_cliente=data["telefono_cliente"],
                email_cliente=data["email_cliente"],
                notas=data.get("notas", ""),
                confirmar_pago_inmediato=True
            )
            detail_serializer = ReservaDetailSerializer(reserva)
            return Response(
                {
                    "mensaje": "¡Reserva confirmada con éxito bajo bloqueo transaccional pesimista!",
                    "reserva": detail_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except ReservaConflictError as e:
            # 409 Conflict: Overbooking bloqueado por concurrencia pesimista
            return Response(
                {
                    "error": "Conflicto de Concurrencia (ISO 27034 R-01)",
                    "detalle": str(e),
                    "codigo": "OVERBOOKING_PREVENTED"
                },
                status=status.HTTP_409_CONFLICT
            )
        except ValidationError as e:
            return Response(
                {"error": "Error de Validación", "detalle": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": "Error Interno del Servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ComprobanteReservaView(TemplateView):
    """
    Vista de comprobante de reserva con código y datos protegidos (PII).
    """
    template_name = "canchas/comprobante.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        codigo = kwargs.get("codigo")
        reserva = get_object_or_404(
            Reserva.objects.select_related("bloque", "bloque__cancha", "bloque__cancha__complejo"),
            codigo=codigo
        )
        context["reserva"] = reserva
        return context
