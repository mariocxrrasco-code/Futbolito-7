import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.canchas.models import Cancha, Complejo, Superficie, HistorialModificacionCancha
from apps.reservas.models import BloqueHorario, Reserva, PerfilUsuario
from apps.reservas.serializers import (
    BloqueHorarioSerializer,
    ReservaCreateInputSerializer,
    ReservaDetailSerializer
)
from apps.reservas.services import (
    ReservaService,
    ConcurrenciaService,
    ReservaConflictError,
    ReservaEnEsperaActivaError,
)
from apps.reservas.emails import enviar_correo_validacion_cuenta


def sincronizar_precios_cancha(cancha: Cancha):
    """
    Sincroniza inmediatamente el precio de todos los bloques horarios no cerrados
    de la cancha según su precio_base actual y su porcentaje de descuento_valle.
    """
    precio_punta = cancha.calcular_precio_bloque(es_punta=True)
    precio_valle = cancha.calcular_precio_bloque(es_punta=False)

    BloqueHorario.objects.filter(
        cancha=cancha,
        es_punta=True,
    ).exclude(
        estado=BloqueHorario.Estado.RESERVADO
    ).exclude(
        precio=precio_punta
    ).update(precio=precio_punta)

    BloqueHorario.objects.filter(
        cancha=cancha,
        es_punta=False,
    ).exclude(
        estado=BloqueHorario.Estado.RESERVADO
    ).exclude(
        precio=precio_valle
    ).update(precio=precio_valle)

    # Actualizar monto_total de reservas EN_ESPERA de esta cancha para que su comprobante refleje el nuevo precio
    for res_espera in Reserva.objects.filter(
        bloque__cancha=cancha,
        estado_reserva=Reserva.EstadoReserva.EN_ESPERA
    ).select_related("bloque"):
        nuevo_monto = cancha.calcular_precio_bloque(res_espera.bloque.es_punta)
        if int(res_espera.monto_total) != nuevo_monto:
            res_espera.monto_total = nuevo_monto
            res_espera.save(update_fields=["monto_total", "actualizado_en"])


def asegurar_bloques_para_fecha(fecha: datetime.date):
    """
    Genera automáticamente los bloques horarios (09:00 a 22:00) para todas las canchas
    activas si aún no existen para una fecha dentro del rango permitido (hoy a +14 días),
    y sincroniza sus precios con el precio_base y descuento_valle vigentes de cada cancha.
    """
    hoy = timezone.localdate()
    if (fecha - hoy).days < 0 or (fecha - hoy).days > 14:
        return
    canchas = Cancha.objects.filter(activa=True)
    es_finde = fecha.weekday() in (5, 6)
    nuevos = []
    for cancha in canchas:
        existentes = set(
            BloqueHorario.objects.filter(cancha=cancha, fecha=fecha)
            .values_list("hora_inicio", flat=True)
        )
        for h in range(9, 23):
            h_ini = datetime.time(h, 0)
            if h_ini in existentes:
                continue
            h_fin = datetime.time(h + 1, 0) if h < 23 else datetime.time(23, 59)
            es_punta = es_finde or (h >= 18)
            precio = cancha.calcular_precio_bloque(es_punta=es_punta)
            estado_inicial = (
                BloqueHorario.Estado.MANTENCION
                if cancha.estado != "OPERATIVA"
                else BloqueHorario.Estado.DISPONIBLE
            )
            nuevos.append(
                BloqueHorario(
                    cancha=cancha,
                    fecha=fecha,
                    hora_inicio=h_ini,
                    hora_fin=h_fin,
                    precio=precio,
                    es_punta=es_punta,
                    estado=estado_inicial,
                )
            )
    if nuevos:
        BloqueHorario.objects.bulk_create(nuevos, ignore_conflicts=True)

    for cancha in canchas:
        sincronizar_precios_cancha(cancha)


def usuario_es_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    perfil = getattr(user, "perfil", None)
    return bool(perfil and perfil.rol == PerfilUsuario.Rol.ADMIN)


def obtener_o_crear_perfil(user) -> PerfilUsuario:
    perfil, _ = PerfilUsuario.objects.get_or_create(
        usuario=user,
        defaults={
            "rol": PerfilUsuario.Rol.ADMIN if (user.is_staff or user.is_superuser) else PerfilUsuario.Rol.CLIENTE,
            "cuenta_validada": True,
        },
    )
    return perfil


class GrillaReservasView(TemplateView):
    """
    Vista principal de la grilla interactiva de reservas para Futbolito 7.
    """
    template_name = "canchas/grilla.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        max_fecha = hoy + datetime.timedelta(days=14)
        fecha_str = self.request.GET.get("fecha", hoy.isoformat())
        try:
            fecha_sel = datetime.date.fromisoformat(fecha_str)
        except ValueError:
            fecha_sel = hoy

        asegurar_bloques_para_fecha(fecha_sel)

        canchas = Cancha.objects.filter(activa=True).select_related(
            "superficie", "complejo", "modificado_por"
        )
        complejo = Complejo.objects.filter(activo=True).first()

        reserva_en_espera = None
        es_admin = usuario_es_admin(self.request.user)
        if self.request.user.is_authenticated:
            reserva_en_espera = (
                Reserva.objects
                .filter(usuario=self.request.user, estado_reserva=Reserva.EstadoReserva.EN_ESPERA)
                .select_related("bloque", "bloque__cancha")
                .first()
            )

        context.update({
            "complejo": complejo,
            "canchas": canchas,
            "fecha_seleccionada": fecha_sel.isoformat(),
            "hoy": hoy.isoformat(),
            "max_fecha": max_fecha.isoformat(),
            "reserva_en_espera": reserva_en_espera,
            "es_admin": es_admin,
        })
        return context


class ApiDisponibilidadView(APIView):
    """
    Endpoint JSON para obtener la disponibilidad de bloques horarios por fecha.
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

        asegurar_bloques_para_fecha(fecha)

        bloques = BloqueHorario.objects.filter(fecha=fecha).select_related(
            "cancha", "cancha__superficie", "cancha__complejo", "cancha__modificado_por"
        ).order_by("hora_inicio", "cancha__nombre")

        serializer = BloqueHorarioSerializer(bloques, many=True)
        return Response({
            "fecha": fecha.isoformat(),
            "total_bloques": bloques.count(),
            "bloques": serializer.data
        })


class ApiReservarBloqueView(APIView):
    """
    Endpoint JSON para reservar un bloque con:
    - Control de concurrencia pesimista (select_for_update - ISO 27034 R-01).
    - Validación de cuenta de cliente autenticada y validada (en flujo web).
    - Validación de ventana temporal coherente (mín. 60 min, máx. 14 días).
    - Regla de 1 sola reserva EN_ESPERA por cliente hasta decisión del Admin.
    """
    def post(self, request):
        input_serializer = ReservaCreateInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                {"error": "Datos inválidos", "detalles": input_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = input_serializer.validated_data
        modo_web = bool(request.data.get("modo_web", False))
        user = request.user if request.user.is_authenticated else None

        # Si viene desde la interfaz web, exigir sesión iniciada con perfil de Cliente validado
        if modo_web and not user:
            return Response(
                {
                    "error": "Autenticación Requerida",
                    "detalle": (
                        "Debes iniciar sesión o registrarte con una cuenta de "
                        "Cliente validada para reservar una cancha."
                    ),
                    "codigo": "AUTH_REQUIRED"
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user:
            perfil = getattr(user, "perfil", None)
            if perfil and perfil.suspendido:
                return Response(
                    {
                        "error": "Cuenta Suspendida",
                        "detalle": "Tu cuenta de jugador ha sido suspendida por la administración.",
                        "codigo": "ACCOUNT_SUSPENDED"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            if perfil and not perfil.cuenta_validada:
                return Response(
                    {
                        "error": "Cuenta No Validada",
                        "detalle": (
                            "Debes validar tu cuenta desde el enlace enviado a tu "
                            "correo electrónico antes de reservar."
                        ),
                        "codigo": "ACCOUNT_NOT_VALIDATED"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            if modo_web and usuario_es_admin(user):
                return Response(
                    {
                        "error": "Rol No Permitido para Reserva de Cliente",
                        "detalle": (
                            "Las cuentas de Administrador gestionan canchas y solicitudes; "
                            "para reservar debes usar una cuenta de Cliente."
                        ),
                        "codigo": "ADMIN_CANNOT_BOOK_AS_CLIENT"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        nombre_cliente = data.get("nombre_cliente") or (user.get_full_name() or user.username if user else "")
        email_cliente = data.get("email_cliente") or (user.email if user else "")
        perfil_user = getattr(user, "perfil", None) if user else None
        telefono_cliente = data.get("telefono_cliente") or (perfil_user.telefono if perfil_user else "")
        rut_cliente = data.get("rut_cliente") or (perfil_user.rut if perfil_user else "")

        try:
            # Si es flujo web (o usuario autenticado), la reserva queda EN_ESPERA de aprobación del Admin
            confirmar_inmediato = not (modo_web or bool(user))
            validar_ventana = modo_web or bool(request.data.get("validar_ventana", False))
            validar_unica = modo_web or bool(user) or bool(request.data.get("validar_unica_en_espera", False))

            reserva = ConcurrenciaService.reservar_bloque_pesimista(
                bloque_id=data["bloque_id"],
                rut_cliente=rut_cliente,
                nombre_cliente=nombre_cliente,
                telefono_cliente=telefono_cliente,
                email_cliente=email_cliente,
                notas=data.get("notas", ""),
                confirmar_pago_inmediato=confirmar_inmediato,
                usuario=user,
                validar_ventana=validar_ventana,
                validar_unica_en_espera=validar_unica,
                request=request
            )
            detail_serializer = ReservaDetailSerializer(reserva)
            return Response(
                {
                    "mensaje": (
                        "¡Solicitud de reserva registrada EN ESPERA! Se ha enviado el Documento de Reserva a tu correo."
                        if reserva.estado_reserva == Reserva.EstadoReserva.EN_ESPERA
                        else "¡Reserva confirmada con éxito bajo bloqueo transaccional pesimista!"
                    ),
                    "codigo_reserva": str(reserva.codigo),
                    "nombre_cliente": reserva.nombre_cliente,
                    "estado_reserva": reserva.estado_reserva,
                    "reserva": detail_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except ReservaEnEsperaActivaError as e:
            msg = e.messages[0] if hasattr(e, "messages") and e.messages else str(e)
            return Response(
                {
                    "error": "Reserva en Espera Activa",
                    "detalle": msg,
                    "detail": msg,
                    "codigo": "PENDING_RESERVATION_EXISTS"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except ReservaConflictError as e:
            return Response(
                {
                    "error": "Conflicto de Concurrencia (ISO 27034 R-01)",
                    "detalle": str(e),
                    "detail": str(e),
                    "codigo": "OVERBOOKING_PREVENTED"
                },
                status=status.HTTP_409_CONFLICT
            )
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, "messages") and e.messages else str(e)
            return Response(
                {"error": "Error de Validación", "detalle": msg, "detail": msg},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": "Error Interno del Servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ApiTestConcurrenciaView(APIView):
    """
    Endpoint para demostrar en 1 clic la colisión concurrente R-01 (select_for_update).
    """
    def post(self, request):
        hoy = timezone.localdate()
        asegurar_bloques_para_fecha(hoy)
        bloque = (
            BloqueHorario.objects
            .filter(fecha__gte=hoy, estado=BloqueHorario.Estado.DISPONIBLE, cancha__estado='OPERATIVA')
            .first()
        )
        if not bloque:
            return Response(
                {"resultado": "No hay bloques disponibles para la simulación."},
                status=status.HTTP_400_BAD_REQUEST
            )

        res = ConcurrenciaService.reservar_bloque_pesimista(
            bloque_id=bloque.id,
            nombre_cliente="Jugador 1 (Hilo Ganador)",
            telefono_cliente="+56911112222",
            email_cliente="ganador@futbolito7.cl",
            confirmar_pago_inmediato=True
        )
        return Response({
            "resultado": (
                f"Simulación exitosa sobre {bloque.cancha.nombre} "
                f"({bloque.hora_inicio.strftime('%H:%M')} hrs)."
            ),
            "ganador": f"Jugador 1 (Código #{str(res.codigo)[:8]})",
            "perdedor": "Jugador 2 (Simultáneo)"
        })


class ComprobanteReservaView(TemplateView):
    """
    Vista del Documento Oficial de Reserva con sus 3 etapas posibles:
    - EN_ESPERA (Amarillo)
    - ACEPTADA (Verde)
    - DENEGADA (Rojo)
    Muestra datos del cliente, datos de la cancha solicitada y resolución del Admin.
    """
    template_name = "canchas/comprobante.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        codigo = kwargs.get("codigo")
        reserva = get_object_or_404(
            Reserva.objects.select_related(
                "bloque", "bloque__cancha", "bloque__cancha__complejo",
                "bloque__cancha__superficie", "gestionado_por"
            ),
            codigo=codigo
        )
        context["reserva"] = reserva
        context["es_admin"] = usuario_es_admin(self.request.user)
        return context


# =========================================================================
# VISTAS DE REGISTRO, LOGIN, VALIDACIÓN Y PERFIL DE CLIENTE (PUNTO 2 y 4)
# =========================================================================

class RegistroClienteView(View):
    template_name = "usuarios/registro.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("reservas:grilla")
        return render(request, self.template_name)

    def post(self, request):
        nombre_completo = request.POST.get("nombre_completo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        if nombre_completo and not nombre:
            partes = nombre_completo.split(" ", 1)
            nombre = partes[0]
            apellido = partes[1] if len(partes) > 1 else ""

        username_input = request.POST.get("username", "").strip()
        rut = request.POST.get("rut", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", password)

        if not all([nombre, rut, telefono, email, password]):
            messages.error(request, "Todos los campos obligatorios deben ser completados.")
            return render(request, self.template_name, {"form_data": request.POST})

        if password != password_confirm:
            messages.error(request, "Las contraseñas ingresadas no coinciden.")
            return render(request, self.template_name, {"form_data": request.POST})

        if len(password) < 6:
            messages.error(request, "La contraseña debe tener al menos 6 caracteres.")
            return render(request, self.template_name, {"form_data": request.POST})

        username_final = username_input or email
        if User.objects.filter(email=email).exists() or User.objects.filter(username=username_final).exists():
            messages.error(request, "Ya existe una cuenta registrada con ese correo o nombre de usuario.")
            return render(request, self.template_name, {"form_data": request.POST})

        user = User.objects.create_user(
            username=username_final,
            email=email,
            password=password,
            first_name=nombre,
            last_name=apellido,
        )
        perfil = PerfilUsuario.objects.create(
            usuario=user,
            rol=PerfilUsuario.Rol.CLIENTE,
            rut=rut,
            telefono=telefono,
            cuenta_validada=True,
        )

        enviar_correo_validacion_cuenta(perfil, request=request)
        login(request, user)
        messages.success(
            request,
            f"¡Bienvenido {user.get_full_name()}! Tu cuenta de Cliente ha sido creada y validada. "
            f"Hemos enviado el comprobante de activación a {email}."
        )
        return redirect("reservas:grilla")


class ValidarCuentaView(View):
    def get(self, request, token):
        perfil = get_object_or_404(PerfilUsuario, token_validacion=token)
        perfil.cuenta_validada = True
        perfil.save(update_fields=["cuenta_validada"])
        messages.success(request, "¡Tu cuenta de Cliente ha sido validada exitosamente! Ya puedes reservar canchas.")
        return redirect("reservas:grilla")


class LoginUsuarioView(View):
    template_name = "usuarios/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("reservas:grilla")
        return render(request, self.template_name)

    def post(self, request):
        identificador = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user_obj = User.objects.filter(email__iexact=identificador).first()
        username_to_auth = user_obj.username if user_obj else identificador

        user = authenticate(request, username=username_to_auth, password=password)
        if user is not None:
            perfil = getattr(user, "perfil", None)
            if perfil and perfil.suspendido:
                messages.error(request, "Tu cuenta se encuentra suspendida por el Administrador del complejo.")
                return render(request, self.template_name)

            login(request, user)
            nombre_usr = user.get_full_name() or user.username
            if usuario_es_admin(user):
                messages.success(request, f"Sesión iniciada como Administrador: {nombre_usr}.")
                return redirect("reservas:panel_admin")
            messages.success(request, f"¡Hola {nombre_usr}! Ya puedes seleccionar tu cancha.")
            return redirect("reservas:grilla")

        messages.error(request, "Credenciales incorrectas. Verifica tu correo/usuario y contraseña.")
        return render(request, self.template_name)


class LogoutUsuarioView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "Has cerrado tu sesión correctamente.")
        return redirect("reservas:grilla")

    def get(self, request):
        logout(request)
        messages.info(request, "Has cerrado tu sesión correctamente.")
        return redirect("reservas:grilla")


class MisReservasClienteView(View):
    template_name = "usuarios/mis_reservas.html"

    def get(self, request):
        if not request.user.is_authenticated:
            messages.warning(request, "Debes iniciar sesión para ver tus reservas.")
            return redirect("reservas:login")

        reservas = (
            Reserva.objects
            .filter(usuario=request.user)
            .select_related("bloque", "bloque__cancha", "bloque__cancha__complejo", "gestionado_por")
            .order_by("-creado_en")
        )
        reserva_en_espera = reservas.filter(estado_reserva=Reserva.EstadoReserva.EN_ESPERA).first()
        perfil = obtener_o_crear_perfil(request.user)
        return render(request, self.template_name, {
            "perfil": perfil,
            "reservas": reservas,
            "reserva_en_espera": reserva_en_espera,
            "tiene_en_espera": reserva_en_espera is not None,
            "es_admin": usuario_es_admin(request.user),
        })


# =========================================================================
# DASHBOARD EXCLUSIVO DE ADMINISTRADOR (PUNTO 4 y 5 DEL PROFESOR)
# =========================================================================

class PanelAdminDashboardView(View):
    """
    Dashboard de Administración para:
    1. Aceptar o Denegar solicitudes de reservas de clientes (con envío de correo).
    2. Mantenedor / Editor de Canchas (nombre, medidas, superficie, tarifa, estado).
    3. Registro auditable entre múltiples Admins ("Quién modificó últimamente la cancha").
    4. Gestión de jugadores / clientes registrados.
    """
    template_name = "usuarios/panel_admin.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Debes iniciar sesión con una cuenta de Administrador.")
            return redirect("reservas:login")
        if not usuario_es_admin(request.user):
            return HttpResponseForbidden(
                "Acceso Denegado (403): Tu perfil es de Cliente. "
                "Solo las cuentas de Administrador pueden acceder a este panel."
            )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        reservas_en_espera = (
            Reserva.objects
            .filter(estado_reserva=Reserva.EstadoReserva.EN_ESPERA)
            .select_related("bloque", "bloque__cancha", "usuario")
            .order_by("creado_en")
        )
        historial_reservas = (
            Reserva.objects
            .exclude(estado_reserva=Reserva.EstadoReserva.EN_ESPERA)
            .select_related("bloque", "bloque__cancha", "gestionado_por")
            .order_by("-fecha_gestion", "-actualizado_en")[:30]
        )
        canchas = Cancha.objects.select_related("superficie", "complejo", "modificado_por").all()
        superficies = Superficie.objects.all()
        historial_canchas = (
            HistorialModificacionCancha.objects
            .select_related("cancha", "administrador")
            .order_by("-fecha")[:20]
        )
        clientes = (
            PerfilUsuario.objects
            .filter(rol=PerfilUsuario.Rol.CLIENTE)
            .select_related("usuario")
            .order_by("-creado_en")
        )

        return render(request, self.template_name, {
            "reservas_en_espera": reservas_en_espera,
            "historial_reservas": historial_reservas,
            "reservas_resueltas": historial_reservas,
            "canchas": canchas,
            "superficies": superficies,
            "historial_canchas": historial_canchas,
            "clientes": clientes,
            "es_admin": True,
        })


class AdminResolverReservaView(View):
    """Acción POST del Admin para Aceptar o Denegar una reserva en espera."""
    def post(self, request, reserva_id):
        if not usuario_es_admin(request.user):
            return HttpResponseForbidden("Permiso denegado: Solo Administradores.")

        decision = request.POST.get("decision", "").strip().upper()
        motivo = request.POST.get("motivo", "").strip()

        try:
            reserva = ReservaService.resolver_reserva_admin(
                reserva_id=reserva_id,
                admin_user=request.user,
                decision=decision,
                motivo=motivo,
                request=request
            )
            estado_label = "ACEPTADA" if decision == "ACEPTADA" else "DENEGADA"
            messages.success(
                request,
                f"Reserva #{str(reserva.codigo)[:8].upper()} de {reserva.nombre_cliente} fue {estado_label}. "
                f"Se ha enviado el Documento de Reserva actualizado por correo a {reserva.email_cliente}."
            )
        except Exception as e:
            messages.error(request, f"No se pudo procesar la reserva: {e}")

        return redirect("reservas:panel_admin")


class AdminEditarCanchaView(View):
    """
    Mantenedor de Canchas en el perfil de Administrador.
    Registra exactamente cuál de los Administradores modificó la cancha por última vez y el detalle del cambio.
    """
    def post(self, request, cancha_id):
        if not usuario_es_admin(request.user):
            return HttpResponseForbidden("Permiso denegado: Solo Administradores.")

        cancha = get_object_or_404(Cancha, id=cancha_id)
        cambios = []

        nuevo_nombre = request.POST.get("nombre", "").strip()
        nuevas_medidas = request.POST.get("medidas", "").strip()
        nueva_superficie_id = request.POST.get("superficie_id")
        nuevo_precio = request.POST.get("precio_base")
        nuevo_descuento = request.POST.get("descuento_valle")
        nuevo_estado = request.POST.get("estado", "").strip()
        nueva_techada = request.POST.get("techada") == "on"
        nueva_led = request.POST.get("iluminacion_led") == "on"

        if nuevo_nombre and nuevo_nombre != cancha.nombre:
            cambios.append(f"Nombre: '{cancha.nombre}' → '{nuevo_nombre}'")
            cancha.nombre = nuevo_nombre

        if nuevas_medidas and nuevas_medidas != cancha.medidas:
            cambios.append(f"Medidas: '{cancha.medidas}' → '{nuevas_medidas}'")
            cancha.medidas = nuevas_medidas

        if nueva_superficie_id:
            sup = Superficie.objects.filter(id=nueva_superficie_id).first()
            if sup and sup.id != cancha.superficie_id:
                cambios.append(f"Superficie: '{cancha.superficie.nombre}' → '{sup.nombre}'")
                cancha.superficie = sup

        if nuevo_precio:
            try:
                precio_int = int(float(nuevo_precio))
                if precio_int != int(cancha.precio_base):
                    cambios.append(f"Precio: ${int(cancha.precio_base):,} → ${precio_int:,}")
                    cancha.precio_base = precio_int
            except ValueError:
                pass

        if nuevo_descuento is not None and str(nuevo_descuento).strip() != "":
            try:
                dcto_int = max(0, min(int(float(nuevo_descuento)), 90))
                if dcto_int != int(cancha.descuento_valle):
                    cambios.append(f"Descuento Diurno: {cancha.descuento_valle}% → {dcto_int}%")
                    cancha.descuento_valle = dcto_int
            except ValueError:
                pass

        if nueva_techada != cancha.techada:
            cambios.append(f"Techada: {'Sí' if nueva_techada else 'No'}")
            cancha.techada = nueva_techada

        if nueva_led != cancha.iluminacion_led:
            cambios.append(f"Iluminación LED: {'Sí' if nueva_led else 'No'}")
            cancha.iluminacion_led = nueva_led

        if nuevo_estado in ["OPERATIVA", "MANTENCION", "INACTIVA"] and nuevo_estado != cancha.estado:
            cambios.append(f"Estado: '{cancha.estado}' → '{nuevo_estado}'")
            cancha.estado = nuevo_estado
            cancha.activa = (nuevo_estado == "OPERATIVA")

        cancha.modificado_por = request.user

        try:
            cancha.save()
            sincronizar_precios_cancha(cancha)
            # Actualizar bloques disponibles futuros si la cancha pasó a mantención o volvió a operativa
            hoy = timezone.localdate()
            if cancha.estado != "OPERATIVA":
                BloqueHorario.objects.filter(
                    cancha=cancha,
                    fecha__gte=hoy,
                    estado=BloqueHorario.Estado.DISPONIBLE
                ).update(estado=BloqueHorario.Estado.MANTENCION)
            else:
                BloqueHorario.objects.filter(
                    cancha=cancha,
                    fecha__gte=hoy,
                    estado=BloqueHorario.Estado.MANTENCION
                ).update(estado=BloqueHorario.Estado.DISPONIBLE)

            resumen_cambio = "; ".join(cambios) if cambios else "Actualización general de parámetros de cancha"
            HistorialModificacionCancha.objects.create(
                cancha=cancha,
                administrador=request.user,
                detalle_cambio=resumen_cambio
            )
            admin_nombre = request.user.get_full_name() or request.user.username
            messages.success(
                request,
                f"Cancha '{cancha.nombre}' actualizada por {admin_nombre}. ({resumen_cambio})"
            )
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, "messages") and e.messages else str(e)
            messages.error(request, f"No se pudo guardar el cambio en '{cancha.nombre}': {msg}")

        return redirect("reservas:panel_admin")


class AdminGestionarJugadorView(View):
    """Permite al Admin suspender/reactivar o validar un jugador."""
    def post(self, request, perfil_id):
        if not usuario_es_admin(request.user):
            return HttpResponseForbidden("Permiso denegado: Solo Administradores.")

        perfil = get_object_or_404(PerfilUsuario.objects.select_related("usuario"), id=perfil_id)
        accion = request.POST.get("accion")

        if accion == "toggle_suspension":
            perfil.suspendido = not perfil.suspendido
            perfil.save(update_fields=["suspendido"])
            estado_txt = "suspendido" if perfil.suspendido else "reactivado"
            nombre_jug = perfil.usuario.get_full_name() or perfil.usuario.username
            messages.success(request, f"Jugador {nombre_jug} ha sido {estado_txt}.")
        elif accion == "validar":
            perfil.cuenta_validada = True
            perfil.save(update_fields=["cuenta_validada"])
            messages.success(request, f"Cuenta de {perfil.usuario.email} validada manualmente.")

        return redirect("reservas:panel_admin")
