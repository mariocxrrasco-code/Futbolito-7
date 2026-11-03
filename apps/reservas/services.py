from datetime import timedelta
from django.db import transaction, OperationalError, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.reservas.models import BloqueHorario, Reserva
from apps.reservas.emails import enviar_correo_documento_reserva


class ReservaConflictError(Exception):
    """Excepción lanzada cuando ocurre un conflicto de concurrencia o sobreventa (ISO 27034 R-01)."""
    pass


class ReservaEnEsperaActivaError(ValidationError):
    """Excepción lanzada cuando el cliente ya tiene una reserva EN_ESPERA sin resolver por el Admin."""
    pass


class VentanaReservaInvalidaError(ValidationError):
    """Excepción lanzada cuando el bloque está fuera de la ventana coherente (<60 min o >14 días)."""
    pass


class ReservaService:
    """
    CONTROL R-01 (ISO 27034): Control de Concurrencia Pesimista en PostgreSQL 16.
    Incluye:
    - Bloqueo atómico select_for_update() (Anti-Overbooking y Anti-Spam 1-Click).
    - Validación de ventana temporal coherente (mín. 60 min, máx. 14 días).
    - Regla de 1 sola reserva EN_ESPERA por cliente hasta decisión del Admin.
    - Flujo de 3 estados (EN_ESPERA, ACEPTADA, DENEGADA) con envío de Documento por correo.
    """

    @staticmethod
    def bloquear_bloque_concurrente(
        bloque_id: int,
        usuario=None,
        tipo_reserva: str = 'B2C',
        rut_cliente: str = "",
        nombre_cliente: str = "",
        telefono_cliente: str = "",
        email_cliente: str = "",
        notas: str = "",
        validar_ventana: bool = False,
        validar_unica_en_espera: bool = False,
        request=None
    ) -> Reserva:
        """
        CONTROL R-01 (ISO 27034): Bloqueo pesimista de fila en PostgreSQL 16.
        Garantiza aislamiento ACID contra carreras críticas (Race Conditions).
        """
        ahora = timezone.now()
        email_limpio = email_cliente.strip().lower() or "cliente@futbolito7.cl"

        try:
            with transaction.atomic():
                # PUNTO 4 DEL PROFESOR: Si el cliente ya tiene una reserva EN_ESPERA, no puede generar otra
                if validar_unica_en_espera or (usuario and getattr(usuario, "is_authenticated", False)):
                    filtro_espera = Reserva.objects.filter(estado_reserva=Reserva.EstadoReserva.EN_ESPERA)
                    if usuario and usuario.is_authenticated:
                        tiene_en_espera = filtro_espera.filter(usuario=usuario).exists()
                    else:
                        tiene_en_espera = filtro_espera.filter(email_cliente=email_limpio).exists()

                    if tiene_en_espera:
                        raise ReservaEnEsperaActivaError(
                            "Ya tienes una solicitud de reserva EN ESPERA de revisión. "
                            "No puedes generar otra reserva hasta que el administrador la acepte o la deniegue."
                        )

                # CAPA BD: SELECT ... FOR UPDATE bloquea la fila a nivel de motor SQL
                try:
                    bloque = (
                        BloqueHorario.objects
                        .select_for_update(nowait=False)
                        .select_related("cancha", "cancha__complejo", "cancha__superficie")
                        .get(id=bloque_id)
                    )
                except BloqueHorario.DoesNotExist:
                    raise ValidationError(
                        "El bloque horario seleccionado no existe.",
                        code='bloque_inexistente'
                    )

                # Verificar que la cancha esté operativa
                if bloque.cancha.estado != 'OPERATIVA' or not bloque.cancha.activa:
                    raise ReservaConflictError("La cancha seleccionada se encuentra en mantención o inactiva.")

                # PUNTO 3 DEL PROFESOR: Validar ventana de tiempo coherente (no <60 min ni >14 días)
                if validar_ventana:
                    es_valido, mensaje_ventana = bloque.validar_ventana_temporal(ahora=ahora)
                    if not es_valido:
                        raise VentanaReservaInvalidaError(mensaje_ventana, code='ventana_invalida')

                # Si está reservado o en mantención
                if bloque.estado == BloqueHorario.Estado.RESERVADO:
                    raise ReservaConflictError(
                        "El bloque horario seleccionado ya fue tomado o se encuentra reservado."
                    )

                if bloque.estado == BloqueHorario.Estado.MANTENCION:
                    raise ReservaConflictError("El bloque horario se encuentra deshabilitado por mantención.")

                # Si está EN_PROCESO_PAGO con bloqueo vigente o reserva EN_ESPERA activa
                if bloque.estado == BloqueHorario.Estado.EN_PROCESO_PAGO:
                    if bloque.reservas.filter(estado_reserva=Reserva.EstadoReserva.EN_ESPERA).exists():
                        raise ReservaConflictError(
                            "El bloque horario ya fue tomado y está en espera de aprobación del administrador."
                        )
                    if bloque.expiracion_bloqueo and ahora < bloque.expiracion_bloqueo:
                        raise ReservaConflictError(
                            "El bloque horario seleccionado ya fue tomado o se encuentra en proceso de pago."
                        )

                # CAPA BACKEND: Cambia estado temporal y define expiración a 10 minutos
                expiracion = ahora + timedelta(minutes=10)
                bloque.estado = BloqueHorario.Estado.EN_PROCESO_PAGO
                bloque.expiracion_bloqueo = expiracion
                bloque.save(update_fields=['estado', 'expiracion_bloqueo', 'actualizado_en'])

                nueva_reserva = Reserva.objects.create(
                    bloque=bloque,
                    usuario=usuario if (usuario and getattr(usuario, 'is_authenticated', False)) else None,
                    tipo_reserva=tipo_reserva,
                    estado_reserva=Reserva.EstadoReserva.EN_ESPERA,
                    rut_cliente=rut_cliente.strip(),
                    nombre_cliente=nombre_cliente.strip() or "Cliente B2C",
                    telefono_cliente=telefono_cliente.strip() or "+56900000000",
                    email_cliente=email_limpio,
                    estado_pago=Reserva.EstadoPago.PENDIENTE,
                    monto_total=bloque.precio,
                    expiracion_bloqueo=expiracion,
                    notas=notas.strip()
                )

                # Enviar correo con el Documento de Reserva en etapa EN_ESPERA
                enviar_correo_documento_reserva(nueva_reserva, request=request)
                return nueva_reserva

        except OperationalError:
            raise ReservaConflictError(
                "Conflicto de concurrencia: El bloque horario se encuentra temporalmente retenido por otra transacción."
            )
        except IntegrityError:
            raise ReservaConflictError(
                "Conflicto de integridad: Este bloque ya cuenta con una reserva activa."
            )

    @classmethod
    def reservar_bloque_pesimista(
        cls,
        bloque_id: int,
        nombre_cliente: str,
        telefono_cliente: str,
        email_cliente: str,
        rut_cliente: str = "",
        notas: str = "",
        confirmar_pago_inmediato: bool = True,
        usuario=None,
        tipo_reserva: str = 'B2C',
        validar_ventana: bool = False,
        validar_unica_en_espera: bool = False,
        request=None
    ) -> Reserva:
        """
        Flujo unificado para la reserva pesimista.
        Si confirmar_pago_inmediato=False (flujo con aprobación de Admin), la reserva
        queda en estado EN_ESPERA hasta que un Administrador la acepte o deniegue.
        """
        if not nombre_cliente or not telefono_cliente or not email_cliente:
            raise ValidationError("Los datos del cliente (nombre, teléfono y correo) son obligatorios.")

        with transaction.atomic():
            reserva = cls.bloquear_bloque_concurrente(
                bloque_id=bloque_id,
                usuario=usuario,
                tipo_reserva=tipo_reserva,
                rut_cliente=rut_cliente,
                nombre_cliente=nombre_cliente,
                telefono_cliente=telefono_cliente,
                email_cliente=email_cliente,
                notas=notas,
                validar_ventana=validar_ventana,
                validar_unica_en_espera=validar_unica_en_espera,
                request=request
            )

            if confirmar_pago_inmediato:
                reserva.estado_pago = Reserva.EstadoPago.PAGADO
                reserva.estado_reserva = Reserva.EstadoReserva.ACEPTADA
                reserva.save(update_fields=['estado_pago', 'estado_reserva', 'actualizado_en'])
                bloque = reserva.bloque
                bloque.estado = BloqueHorario.Estado.RESERVADO
                bloque.expiracion_bloqueo = None
                bloque.save(update_fields=['estado', 'expiracion_bloqueo', 'actualizado_en'])

            return reserva

    @staticmethod
    def resolver_reserva_admin(
        reserva_id: int,
        admin_user,
        decision: str,
        motivo: str = "",
        request=None
    ) -> Reserva:
        """
        PUNTO 4 y 5 DEL PROFESOR:
        Permite al Administrador ACEPTAR o DENEGAR una solicitud de reserva que está EN_ESPERA.
        - Si se ACEPTA: Bloque pasa a RESERVADO, reserva pasa a ACEPTADA y se notifica por correo.
        - Si se DENIEGA: Bloque se libera a DISPONIBLE, reserva pasa a DENEGADA y el cliente ya puede pedir otra hora.
        """
        if decision not in [Reserva.EstadoReserva.ACEPTADA, Reserva.EstadoReserva.DENEGADA]:
            raise ValidationError("La decisión debe ser 'ACEPTADA' o 'DENEGADA'.")

        with transaction.atomic():
            reserva = (
                Reserva.objects
                .select_for_update()
                .select_related("bloque", "bloque__cancha", "bloque__cancha__complejo", "bloque__cancha__superficie")
                .get(id=reserva_id)
            )
            bloque = BloqueHorario.objects.select_for_update().get(id=reserva.bloque_id)

            reserva.estado_reserva = decision
            reserva.gestionado_por = admin_user
            reserva.fecha_gestion = timezone.now()
            reserva.motivo_decision = motivo.strip()

            if decision == Reserva.EstadoReserva.ACEPTADA:
                reserva.estado_pago = Reserva.EstadoPago.PAGADO
                bloque.estado = BloqueHorario.Estado.RESERVADO
                bloque.expiracion_bloqueo = None
            else:
                reserva.estado_pago = Reserva.EstadoPago.CANCELADO
                bloque.estado = BloqueHorario.Estado.DISPONIBLE
                bloque.expiracion_bloqueo = None

            bloque.save(update_fields=['estado', 'expiracion_bloqueo', 'actualizado_en'])
            reserva.save()

            # Enviar correo al cliente con su Documento de Reserva actualizado (ACEPTADA o DENEGADA)
            enviar_correo_documento_reserva(reserva, request=request)
            return reserva


# Alias para compatibilidad
ConcurrenciaService = ReservaService
