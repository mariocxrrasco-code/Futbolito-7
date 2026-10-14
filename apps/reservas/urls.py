from django.urls import path
from apps.reservas.views import (
    GrillaReservasView,
    ApiDisponibilidadView,
    ApiReservarBloqueView,
    ComprobanteReservaView
)

app_name = "reservas"

urlpatterns = [
    path("", GrillaReservasView.as_view(), name="grilla"),
    path("comprobante/<uuid:codigo>/", ComprobanteReservaView.as_view(), name="comprobante"),
    # Endpoints REST API
    path("api/disponibilidad/", ApiDisponibilidadView.as_view(), name="api_disponibilidad"),
    path("api/reservar/", ApiReservarBloqueView.as_view(), name="api_reservar"),
]
