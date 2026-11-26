import datetime
import logging
import math
import re
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import UserRateThrottle

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

logger = logging.getLogger(__name__)


class ReservarRateThrottle(UserRateThrottle):
    scope = "reservar"


def _obtener_ip_cliente(request) -> str:
    """Extrae y normaliza la IP del cliente de forma segura para claves de caché."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_raw = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "unknown")
    return re.sub(r"[^a-zA-Z0-9.:_-]", "", ip_raw)[:45] or "unknown"


def _registrar_fallo_rate_limit(cache_key: str, ventana_seg: int) -> int:
    actual = cache.get(cache_key, 0) + 1
    cache.set(cache_key, actual, timeout=ventana_seg)
    return actual


def sincronizar_precios_cancha(cancha: Cancha):
    """
    Sincroniza inmediatamente el precio de todos los bloques horarios y reservas
    de la cancha con su precio_base fijo actual.
    """
    precio_fijo = int(cancha.precio_base)

    BloqueHorario.objects.filter(
        cancha=cancha,
    ).exclude(
        precio=precio_fijo
    ).update(precio=precio_fijo)

    Reserva.objects.filter(
        bloque__cancha=cancha,
    ).exclude(
        monto_total=precio_fijo
    ).update(monto_total=precio_fijo)


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
    permission_classes = [AllowAny]

    def get(self, request):
        fecha_str = request.query_params.get("fecha")
        if not fecha_str:
            fecha = timezone.localdate()
        else:
            if len(fecha_str) > 10:
                return Response(
                    {"error": "Formato de fecha inválido. Utilice YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
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
    Endpoint JSON protegido para reservar un bloque con:
    - Autenticación obligatoria de Cliente validado (sin bypass de modo_web).
    - Control de concurrencia pesimista (select_for_update - ISO 27034 R-01).
    - Validación obligatoria de ventana temporal (mín. 60 min, máx. 14 días).
    - Regla obligatoria de 1 sola reserva EN_ESPERA por cliente hasta decisión del Admin.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ReservarRateThrottle]

    def post(self, request):
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response(
                {
                    "error": "Autenticación Requerida",
                    "detalle": (
                        "Debes iniciar sesión o registrarte con una cuenta de "
                        "Cliente validada para reservar una cancha."
                    ),
                    "detail": (
                        "Debes iniciar sesión o registrarte con una cuenta de "
                        "Cliente validada para reservar una cancha."
                    ),
                    "codigo": "AUTH_REQUIRED"
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        perfil = getattr(user, "perfil", None)
        if perfil and perfil.suspendido:
            return Response(
                {
                    "error": "Cuenta Suspendida",
                    "detalle": "Tu cuenta de jugador ha sido suspendida por la administración.",
                    "detail": "Tu cuenta de jugador ha sido suspendida por la administración.",
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
                    "detail": (
                        "Debes validar tu cuenta desde el enlace enviado a tu "
                        "correo electrónico antes de reservar."
                    ),
                    "codigo": "ACCOUNT_NOT_VALIDATED"
                },
                status=status.HTTP_403_FORBIDDEN
            )
        if usuario_es_admin(user):
            return Response(
                {
                    "error": "Rol No Permitido para Reserva de Cliente",
                    "detalle": (
                        "Las cuentas de Administrador gestionan canchas y solicitudes; "
                        "para reservar debes usar una cuenta de Cliente."
                    ),
                    "detail": (
                        "Las cuentas de Administrador gestionan canchas y solicitudes; "
                        "para reservar debes usar una cuenta de Cliente."
                    ),
                    "codigo": "ADMIN_CANNOT_BOOK_AS_CLIENT"
                },
                status=status.HTTP_403_FORBIDDEN
            )

        input_serializer = ReservaCreateInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                {"error": "Datos inválidos", "detalles": input_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = input_serializer.validated_data

        # Identidad derivada estrictamente del usuario autenticado (evita suplantación vía proxy)
        nombre_cliente = user.get_full_name() or user.username
        email_cliente = user.email
        telefono_cliente = perfil.telefono if perfil else ""
        rut_cliente = perfil.rut if perfil else ""

        notas_raw = (data.get("notas") or "").strip()
        if len(notas_raw) > 100 or (notas_raw and not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ0-9\s]+$", notas_raw)):
            return Response(
                {
                    "error": "Notas Inválidas",
                    "detalle": (
                        "En las notas de partido solo se permiten letras, números y espacios "
                        "(máx. 100 caracteres, sin símbolos)."
                    ),
                    "detail": (
                        "En las notas de partido solo se permiten letras, números y espacios "
                        "(máx. 100 caracteres, sin símbolos)."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            reserva = ConcurrenciaService.reservar_bloque_pesimista(
                bloque_id=data["bloque_id"],
                rut_cliente=rut_cliente,
                nombre_cliente=nombre_cliente,
                telefono_cliente=telefono_cliente,
                email_cliente=email_cliente,
                notas=notas_raw,
                confirmar_pago_inmediato=False,
                usuario=user,
                validar_ventana=True,
                validar_unica_en_espera=True,
                request=request
            )
            detail_serializer = ReservaDetailSerializer(reserva)
            return Response(
                {
                    "mensaje": (
                        "¡Solicitud de reserva registrada EN ESPERA! "
                        "Se ha enviado el Documento de Reserva a tu correo."
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
        except Exception:
            logger.exception("Error inesperado al procesar reserva para usuario %s", user.pk)
            return Response(
                {
                    "error": "Error Interno del Servidor",
                    "detalle": "No se pudo procesar la reserva en este momento. Intenta nuevamente.",
                    "detail": "No se pudo procesar la reserva en este momento. Intenta nuevamente.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ApiTestConcurrenciaView(APIView):
    """
    Endpoint restringido exclusivamente a Administradores para demostrar colisión R-01.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Autenticación requerida."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        if not usuario_es_admin(request.user):
            return Response(
                {"error": "Acceso denegado: solo Administradores pueden ejecutar esta simulación."},
                status=status.HTTP_403_FORBIDDEN
            )

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


class ComprobanteReservaView(View):
    """
    Vista protegida (Anti-IDOR) del Documento Oficial de Reserva.
    Solo accesible por el titular de la reserva o por un Administrador.
    """
    template_name = "canchas/comprobante.html"

    def get(self, request, codigo):
        if not request.user.is_authenticated:
            messages.warning(request, "Debes iniciar sesión para visualizar el comprobante de reserva.")
            return redirect(f"{reverse('reservas:login')}?next={request.path}")

        reserva = get_object_or_404(
            Reserva.objects.select_related(
                "bloque", "bloque__cancha", "bloque__cancha__complejo",
                "bloque__cancha__superficie", "gestionado_por"
            ),
            codigo=codigo
        )

        es_admin = usuario_es_admin(request.user)
        if not es_admin and reserva.usuario_id != request.user.id:
            return render(request, "403.html", status=403)

        return render(request, self.template_name, {
            "reserva": reserva,
            "es_admin": es_admin,
        })


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
        ip_cliente = _obtener_ip_cliente(request)
        reg_key = f"rl:registro:{ip_cliente}"
        if cache.get(reg_key, 0) >= 8:
            messages.error(
                request,
                "⚠️ Demasiados intentos de registro desde esta red. Intenta nuevamente en 10 minutos."
            )
            return render(request, self.template_name, {"form_data": request.POST}, status=429)
        _registrar_fallo_rate_limit(reg_key, 600)

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

        nombre_validar = nombre_completo or f"{nombre} {apellido}".strip()
        if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{3,80}$", nombre_validar):
            messages.error(
                request,
                "En el Nombre Completo solo se permiten letras y espacios (sin números ni símbolos)."
            )
            return render(request, self.template_name, {"form_data": request.POST})

        if username_input and not re.match(r"^[a-zA-Z0-9._]{3,30}$", username_input):
            messages.error(
                request,
                "En el Nombre de Usuario solo se permiten letras, números, punto (.) y guion bajo (_), sin espacios."
            )
            return render(request, self.template_name, {"form_data": request.POST})

        if not re.match(r"^\d{2}\.\d{3}\.\d{3}-[\dkK]$", rut):
            messages.error(
                request,
                "El RUT debe tener obligatoriamente el formato chileno XX.XXX.XXX-X "
                "(9 dígitos, 2 puntos y 1 guion, ej: 21.123.456-7)."
            )
            return render(request, self.template_name, {"form_data": request.POST})

        if not re.match(r"^[+0-9\s]{8,16}$", telefono) or len(re.sub(r"\D", "", telefono)) < 8:
            messages.error(request, "En el Teléfono Móvil solo se permiten números y el signo + (mínimo 8 dígitos).")
            return render(request, self.template_name, {"form_data": request.POST})

        if len(email) > 150 or not re.match(r"^[a-zA-Z0-9._+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
            messages.error(request, "Ingresa un correo electrónico válido sin espacios ni símbolos prohibidos.")
            return render(request, self.template_name, {"form_data": request.POST})

        if password != password_confirm:
            messages.error(request, "Las contraseñas ingresadas no coinciden.")
            return render(request, self.template_name, {"form_data": request.POST})

        if len(password) < 8 or len(password) > 16:
            messages.error(request, "La contraseña debe tener entre 8 y 16 caracteres.")
            return render(request, self.template_name, {"form_data": request.POST})

        if not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            messages.error(request, "La contraseña debe incluir obligatorio al menos 1 letra mayúscula y 1 número.")
            return render(request, self.template_name, {"form_data": request.POST})

        username_final = username_input or email
        if User.objects.filter(email=email).exists() or User.objects.filter(username=username_final).exists():
            messages.error(request, "Ya existe una cuenta registrada con ese correo o nombre de usuario.")
            return render(request, self.template_name, {"form_data": request.POST})

        try:
            user = User.objects.create_user(
                username=username_final,
                email=email,
                password=password,
                first_name=nombre[:80],
                last_name=apellido[:80],
            )
            perfil = PerfilUsuario.objects.create(
                usuario=user,
                rol=PerfilUsuario.Rol.CLIENTE,
                rut=rut,
                telefono=telefono,
                cuenta_validada=False,
            )
        except IntegrityError:
            messages.error(request, "Ya existe una cuenta registrada con esos datos.")
            return render(request, self.template_name, {"form_data": request.POST})

        enviar_correo_validacion_cuenta(perfil, request=request)
        messages.success(
            request,
            f"¡Cuenta creada para {user.get_full_name()}! Hemos enviado un enlace de validación a {email}. "
            f"Debes abrir ese correo y hacer clic en 'Validar mi Cuenta' para poder iniciar sesión."
        )
        return redirect("reservas:login")


class ValidarCuentaView(View):
    """
    Activa una cuenta nueva con token UUID de un solo uso (rota token al activarse
    y bloquea activación o autologin si la cuenta está suspendida o ya validada).
    """
    def get(self, request, token):
        perfil = get_object_or_404(PerfilUsuario.objects.select_related("usuario"), token_validacion=token)

        if perfil.suspendido:
            messages.error(request, "Tu cuenta se encuentra suspendida por el Administrador del complejo.")
            return redirect("reservas:login")

        if perfil.cuenta_validada:
            messages.info(request, "Esta cuenta ya fue validada anteriormente. Inicia sesión con tu contraseña.")
            return redirect("reservas:login")

        perfil.cuenta_validada = True
        perfil.token_validacion = uuid.uuid4()
        perfil.save(update_fields=["cuenta_validada", "token_validacion"])
        login(request, perfil.usuario)
        messages.success(
            request,
            f"¡Correo validado exitosamente, {perfil.usuario.get_full_name() or perfil.usuario.username}! "
            f"Tu cuenta de Cliente ya está activa y puedes reservar canchas."
        )
        return redirect("reservas:grilla")


class LoginUsuarioView(View):
    template_name = "usuarios/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("reservas:grilla")
        return render(request, self.template_name)

    def post(self, request):
        ip_cliente = _obtener_ip_cliente(request)
        identificador = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not identificador or not password:
            messages.error(request, "Debes ingresar tu usuario/correo y contraseña.")
            return render(request, self.template_name)

        ip_key = f"rl:login:ip:{ip_cliente}"
        if cache.get(ip_key, 0) >= 15:
            messages.error(
                request,
                "⚠️ Demasiados intentos fallidos de inicio de sesión. "
                "Por seguridad, espera 5 minutos antes de volver a intentar."
            )
            return render(request, self.template_name, status=429)

        if len(identificador) > 100 or not re.match(r"^[a-zA-Z0-9@._+\-]+$", identificador):
            _registrar_fallo_rate_limit(ip_key, 300)
            messages.error(
                request,
                "⚠️ Entrada bloqueada por seguridad: el usuario o correo contiene caracteres no permitidos."
            )
            return render(request, self.template_name)

        if len(password) > 64 or any(c in password for c in ("<", ">", "\x00")):
            _registrar_fallo_rate_limit(ip_key, 300)
            messages.error(
                request,
                "⚠️ Entrada bloqueada por seguridad: la contraseña contiene caracteres no válidos."
            )
            return render(request, self.template_name)

        acct_key = f"rl:login:acct:{ip_cliente}:{identificador.lower()}"
        if cache.get(acct_key, 0) >= 5:
            messages.error(
                request,
                "⚠️ Cuenta bloqueada temporalmente por demasiados intentos fallidos. "
                "Intenta nuevamente en 5 minutos."
            )
            return render(request, self.template_name, status=429)

        user_obj = User.objects.filter(email__iexact=identificador).first()
        username_to_auth = user_obj.username if user_obj else identificador

        user = authenticate(request, username=username_to_auth, password=password)
        if user is not None:
            perfil = getattr(user, "perfil", None)
            if perfil and perfil.suspendido:
                messages.error(request, "Tu cuenta se encuentra suspendida por el Administrador del complejo.")
                return render(request, self.template_name)

            if perfil and not usuario_es_admin(user) and not perfil.cuenta_validada:
                enviar_correo_validacion_cuenta(perfil, request=request)
                messages.error(
                    request,
                    f"⚠️ Tu cuenta aún no ha sido validada. Revisa tu bandeja de correo ({user.email}) "
                    f"y haz clic en el botón 'Validar mi Cuenta' antes de iniciar sesión."
                )
                return render(request, self.template_name)

            cache.delete(acct_key)
            login(request, user)
            nombre_usr = user.get_full_name() or user.username

            next_url = request.POST.get("next") or request.GET.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)

            if usuario_es_admin(user):
                messages.success(request, f"Sesión iniciada como Administrador: {nombre_usr}.")
                return redirect("reservas:panel_admin")
            messages.success(request, f"¡Hola {nombre_usr}! Ya puedes seleccionar tu cancha.")
            return redirect("reservas:grilla")

        _registrar_fallo_rate_limit(ip_key, 300)
        _registrar_fallo_rate_limit(acct_key, 300)
        messages.error(request, "Credenciales incorrectas. Verifica tu correo/usuario y contraseña.")
        return render(request, self.template_name)


class LogoutUsuarioView(View):
    """Cierre de sesión protegido exclusivamente vía POST con CSRF (evita Logout CSRF por GET)."""
    def post(self, request):
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

        if decision not in (Reserva.EstadoReserva.ACEPTADA, Reserva.EstadoReserva.DENEGADA):
            messages.error(request, "⚠️ Decisión administrativa inválida.")
            return redirect("reservas:panel_admin")

        if any(c in motivo for c in ("<", ">", "\x00")) or len(motivo) > 255:
            messages.error(request, "⚠️ Entrada bloqueada: la observación contiene caracteres no permitidos.")
            return redirect("reservas:panel_admin")

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
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, "messages") and e.messages else str(e)
            messages.error(request, f"No se pudo procesar la reserva: {msg}")
        except Exception:
            logger.exception("Error inesperado al resolver reserva %s", reserva_id)
            messages.error(request, "No se pudo procesar la reserva por un error interno controlado.")

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

        if any(any(ch in campo for ch in ("<", ">", "\x00")) for campo in (nuevo_nombre, nuevas_medidas)):
            messages.error(request, "⚠️ Entrada bloqueada: el nombre o las medidas contienen caracteres no permitidos.")
            return redirect("reservas:panel_admin")

        if len(nuevo_nombre) > 100 or len(nuevas_medidas) > 60:
            messages.error(
                request,
                "⚠️ Entrada bloqueada: el nombre (máx. 100) o las medidas (máx. 60) exceden el límite."
            )
            return redirect("reservas:panel_admin")

        nueva_superficie_id = (request.POST.get("superficie_id") or "").strip()
        nuevo_precio = (request.POST.get("precio_base") or "").strip()
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
            if not nueva_superficie_id.isdigit():
                messages.error(request, "⚠️ Superficie seleccionada inválida.")
                return redirect("reservas:panel_admin")
            sup = Superficie.objects.filter(id=int(nueva_superficie_id)).first()
            if sup and sup.id != cancha.superficie_id:
                cambios.append(f"Superficie: '{cancha.superficie.nombre}' → '{sup.nombre}'")
                cancha.superficie = sup

        if nuevo_precio:
            try:
                precio_float = float(nuevo_precio)
                if not math.isfinite(precio_float) or precio_float < 0 or precio_float > 5_000_000:
                    messages.error(request, "⚠️ El precio debe estar entre $0 y $5.000.000 CLP.")
                    return redirect("reservas:panel_admin")
                precio_int = int(precio_float)
                if precio_int != int(cancha.precio_base):
                    cambios.append(f"Precio: ${int(cancha.precio_base):,} → ${precio_int:,}")
                    cancha.precio_base = precio_int
            except (ValueError, OverflowError):
                messages.error(request, "⚠️ Formato de precio inválido.")
                return redirect("reservas:panel_admin")

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
                detalle_cambio=resumen_cambio[:255]
            )
            admin_nombre = request.user.get_full_name() or request.user.username
            messages.success(
                request,
                f"Cancha '{cancha.nombre}' actualizada por {admin_nombre}. ({resumen_cambio})"
            )
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, "messages") and e.messages else str(e)
            messages.error(request, f"No se pudo guardar el cambio en '{cancha.nombre}': {msg}")
        except IntegrityError:
            messages.error(request, "No se pudo guardar el cambio: ya existe otra cancha con ese nombre.")

        return redirect("reservas:panel_admin")


class AdminGestionarJugadorView(View):
    """Permite al Admin suspender/reactivar o validar un jugador (protegido contra modificar Admins)."""
    def post(self, request, perfil_id):
        if not usuario_es_admin(request.user):
            return HttpResponseForbidden("Permiso denegado: Solo Administradores.")

        perfil = get_object_or_404(PerfilUsuario.objects.select_related("usuario"), id=perfil_id)
        if perfil.es_admin or perfil.usuario_id == request.user.id:
            return HttpResponseForbidden("Acción no permitida sobre cuentas de Administrador.")

        accion = (request.POST.get("accion") or "").strip()

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
        else:
            messages.error(request, "⚠️ Acción administrativa no reconocida.")

        return redirect("reservas:panel_admin")
