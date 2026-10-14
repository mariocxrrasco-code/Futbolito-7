from datetime import timedelta
from django.db import transaction, OperationalError, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.reservas.models import BloqueHorario, Reserva


class ReservaConflictError(Exception):
    """Excepción lanzada cuando ocurre un conflicto de concurrencia o sobreventa (ISO 27034 R-01)."""
    pass


class ReservaService:
    """
    CONTROL R-01 (ISO 27034): Control de Concurrencia Pesimista en PostgreSQL 16.
    Aislamiento ACID contra carreras críticas (Race Conditions) y sobreventa (Overbooking).
    """

    @staticmethod
    def bloquear_bloque_concurrente(
        bloque_id: int,
        usuario=None,
        tipo_reserva: str = 'B2C',
        nombre_cliente: str = "",
        telefono_cliente: str = "",
        email_cliente: str = "",
        notas: str = ""
    ) -> Reserva:
        """
        CONTROL R-01 (ISO 27034): Bloqueo pesimista de fila en PostgreSQL 16.
        Garantiza aislamiento ACID contra carreras críticas (Race Conditions).
        Aplica retención temporal de 10 minutos en estado 'EN_PROCESO_PAGO'.
        """
        ahora = timezone.now()

        try:
            with transaction.atomic():
                # CAPA BD: SELECT ... FOR UPDATE bloquea la fila a nivel de motor SQL
                try:
                    # Permite tomar bloques 'DISPONIBLE' o con bloqueo temporal expirado (>10 min)
                    bloque = (
                        BloqueHorario.objects
                        .select_for_update(nowait=False)
                        .select_related("cancha", "cancha__complejo")
                        .get(id=bloque_id)
                    )
                except BloqueHorario.DoesNotExist:
                    raise ValidationError(
                        "El bloque horario seleccionado no existe.",
                        code='bloque_inexistente'
                    )

                # Si está reservado o en mantención
                if bloque.estado == BloqueHorario.Estado.RESERVADO:
                    raise ReservaConflictError(
                        f"El bloque horario seleccionado ya fue tomado o se encuentra en proceso de pago."
                    )

                if bloque.estado == BloqueHorario.Estado.MANTENCION:
                    raise ReservaConflictError("El bloque horario se encuentra deshabilitado por mantención.")

                # Si está EN_PROCESO_PAGO pero el bloqueo de 10 minutos aún está vigente
                if bloque.estado == BloqueHorario.Estado.EN_PROCESO_PAGO:
                    if bloque.expiracion_bloqueo and ahora < bloque.expiracion_bloqueo:
                        raise ReservaConflictError(
                            "El bloque horario seleccionado ya fue tomado o se encuentra en proceso de pago."
                        )

                # CAPA BACKEND: Cambia estado temporal y define expiración a 10 minutos
                expiracion = ahora + timedelta(minutes=10)
                bloque.estado = BloqueHorario.Estado.EN_PROCESO_PAGO
                bloque.expiracion_bloqueo = expiracion
                bloque.save(update_fields=['estado', 'expiracion_bloqueo', 'actualizado_en'])

                # Si ya existía una reserva previa pendiente expirada, limpiarla o actualizar
                Reserva.objects.filter(bloque=bloque, estado_pago=Reserva.EstadoPago.PENDIENTE).delete()

                nueva_reserva = Reserva.objects.create(
                    bloque=bloque,
                    usuario=usuario,
                    tipo_reserva=tipo_reserva,
                    nombre_cliente=nombre_cliente.strip() or "Cliente B2C",
                    telefono_cliente=telefono_cliente.strip() or "+56900000000",
                    email_cliente=email_cliente.strip().lower() or "cliente@futbolito7.cl",
                    estado_pago=Reserva.EstadoPago.PENDIENTE,
                    monto_total=bloque.precio,
                    expiracion_bloqueo=expiracion,
                    notas=notas.strip()
                )
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
        notas: str = "",
        confirmar_pago_inmediato: bool = True,
        usuario=None,
        tipo_reserva: str = 'B2C'
    ) -> Reserva:
        """
        Flujo unificado para la reserva pesimista con opción de confirmación inmediata de pago.
        """
        if not nombre_cliente or not telefono_cliente or not email_cliente:
            raise ValidationError("Los datos del cliente (nombre, teléfono y correo) son obligatorios.")

        with transaction.atomic():
            reserva = cls.bloquear_bloque_concurrente(
                bloque_id=bloque_id,
                usuario=usuario,
                tipo_reserva=tipo_reserva,
                nombre_cliente=nombre_cliente,
                telefono_cliente=telefono_cliente,
                email_cliente=email_cliente,
                notas=notas
            )

            if confirmar_pago_inmediato:
                reserva.estado_pago = Reserva.EstadoPago.PAGADO
                reserva.save(update_fields=['estado_pago', 'actualizado_en'])
                bloque = reserva.bloque
                bloque.estado = BloqueHorario.Estado.RESERVADO
                bloque.expiracion_bloqueo = None
                bloque.save(update_fields=['estado', 'expiracion_bloqueo', 'actualizado_en'])

            return reserva


# Alias para compatibilidad
ConcurrenciaService = ReservaService
