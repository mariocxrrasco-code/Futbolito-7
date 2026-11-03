from django.urls import path
from apps.reservas.views import (
    GrillaReservasView,
    ApiDisponibilidadView,
    ApiReservarBloqueView,
    ApiTestConcurrenciaView,
    ComprobanteReservaView,
    RegistroClienteView,
    ValidarCuentaView,
    LoginUsuarioView,
    LogoutUsuarioView,
    MisReservasClienteView,
    PanelAdminDashboardView,
    AdminResolverReservaView,
    AdminEditarCanchaView,
    AdminGestionarJugadorView,
)

app_name = "reservas"

urlpatterns = [
    path("", GrillaReservasView.as_view(), name="grilla"),
    path("comprobante/<uuid:codigo>/", ComprobanteReservaView.as_view(), name="comprobante"),
    # Autenticación y Perfiles (Cliente vs Admin)
    path("registro/", RegistroClienteView.as_view(), name="registro"),
    path("validar-cuenta/<uuid:token>/", ValidarCuentaView.as_view(), name="validar_cuenta"),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", LogoutUsuarioView.as_view(), name="logout"),
    path("mis-reservas/", MisReservasClienteView.as_view(), name="mis_reservas"),
    # Panel Administrador (Mantenedor Canchas, Auditoría Multi-Admin, Aceptar/Denegar Reservas y Jugadores)
    path("panel-admin/", PanelAdminDashboardView.as_view(), name="panel_admin"),
    path(
        "panel-admin/reserva/<int:reserva_id>/resolver/",
        AdminResolverReservaView.as_view(),
        name="admin_resolver_reserva",
    ),
    path("panel-admin/cancha/<int:cancha_id>/editar/", AdminEditarCanchaView.as_view(), name="admin_editar_cancha"),
    path(
        "panel-admin/jugador/<int:perfil_id>/gestionar/",
        AdminGestionarJugadorView.as_view(),
        name="admin_gestionar_jugador",
    ),
    # Endpoints REST API
    path("api/disponibilidad/", ApiDisponibilidadView.as_view(), name="api_disponibilidad"),
    path("api/reservar/", ApiReservarBloqueView.as_view(), name="api_reservar"),
    path("api/test-concurrencia/", ApiTestConcurrenciaView.as_view(), name="api_test_concurrencia"),
]
