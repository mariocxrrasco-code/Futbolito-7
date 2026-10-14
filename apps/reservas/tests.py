import datetime
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
import concurrent.futures

from apps.canchas.models import Complejo, Superficie, Cancha
from apps.reservas.models import BloqueHorario, Reserva
from apps.reservas.services import ReservaService, ConcurrenciaService, ReservaConflictError


class ReservasModelAndServiceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.complejo = Complejo.objects.create(
            nombre="Complejo Deportivo Central",
            direccion="Av. Siempre Viva 742",
            comuna="Santiago"
        )
        self.superficie = Superficie.objects.create(nombre="Pasto Sintético Pro")
        self.cancha = Cancha.objects.create(
            complejo=self.complejo,
            nombre="Cancha 1",
            superficie=self.superficie,
            precio_base=36000,
            estado='OPERATIVA'
        )
        self.hoy = timezone.localdate()
        self.bloque = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=self.hoy,
            hora_inicio=datetime.time(19, 0),
            hora_fin=datetime.time(20, 0),
            precio=36000,
            es_punta=True,
            estado=BloqueHorario.Estado.DISPONIBLE
        )

    def test_bloque_disponibilidad(self):
        """Verifica el cálculo de disponibilidad de BloqueHorario con EN_PROCESO_PAGO."""
        self.assertTrue(self.bloque.esta_disponible())

        # Bloqueo temporal expirado (>10 min) debe volver a considerarse disponible
        self.bloque.estado = BloqueHorario.Estado.EN_PROCESO_PAGO
        self.bloque.expiracion_bloqueo = timezone.now() - datetime.timedelta(minutes=1)
        self.bloque.save()
        self.assertTrue(self.bloque.esta_disponible())

        # Bloqueo temporal vigente (<=10 min) NO está disponible
        self.bloque.expiracion_bloqueo = timezone.now() + datetime.timedelta(minutes=10)
        self.bloque.save()
        self.assertFalse(self.bloque.esta_disponible())

        # Bloque reservado NO está disponible
        self.bloque.estado = BloqueHorario.Estado.RESERVADO
        self.bloque.save()
        self.assertFalse(self.bloque.esta_disponible())

    def test_bloquear_bloque_concurrente_r01_10_minutos(self):
        """
        CONTROL R-01 (ISO 27034):
        Verifica el método oficial ReservaService.bloquear_bloque_concurrente() con ventana de 10 min.
        """
        reserva = ReservaService.bloquear_bloque_concurrente(
            bloque_id=self.bloque.id,
            nombre_cliente="Mario Carrasco",
            telefono_cliente="+56998765432",
            email_cliente="mario.carrasco@correo.cl",
            tipo_reserva="B2C"
        )

        self.assertEqual(reserva.estado_pago, Reserva.EstadoPago.PENDIENTE)
        self.assertEqual(reserva.tipo_reserva, "B2C")
        self.assertIsNotNone(reserva.expiracion_bloqueo)

        # El bloque debe quedar en EN_PROCESO_PAGO
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.estado, BloqueHorario.Estado.EN_PROCESO_PAGO)
        self.assertFalse(self.bloque.esta_disponible())

        # Intento de segundo usuario simultáneo debe fallar por colisión R-01
        with self.assertRaises(ReservaConflictError):
            ReservaService.bloquear_bloque_concurrente(
                bloque_id=self.bloque.id,
                nombre_cliente="Segundo Cliente",
                telefono_cliente="+56911112222",
                email_cliente="segundo@correo.cl"
            )

    def test_reservar_bloque_pesimista_exito(self):
        """Verifica el flujo exitoso de reserva atómica y confirmación inmediata."""
        reserva = ReservaService.reservar_bloque_pesimista(
            bloque_id=self.bloque.id,
            nombre_cliente="Mario Carrasco",
            telefono_cliente="+56998765432",
            email_cliente="mario.carrasco@correo.cl",
            notas="Partido de prueba",
            confirmar_pago_inmediato=True
        )

        self.assertIsNotNone(reserva.codigo)
        self.assertEqual(reserva.estado_pago, Reserva.EstadoPago.PAGADO)
        self.assertEqual(reserva.monto_total, 36000)

        # El bloque horario debe cambiar a RESERVADO
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.estado, BloqueHorario.Estado.RESERVADO)
        self.assertFalse(self.bloque.esta_disponible())

    def test_enmascaramiento_pii_iso27034(self):
        """Verifica que los datos personales sensibles se enmascaren correctamente."""
        reserva = Reserva(
            bloque=self.bloque,
            nombre_cliente="Paulo Alegría",
            telefono_cliente="+56987654321",
            email_cliente="paulo.alegria@empresa.com",
            monto_total=36000
        )
        self.assertEqual(reserva.email_enmascarado, "p***a@empresa.com")
        self.assertEqual(reserva.telefono_enmascarado, "+569 **** 4321")

    def test_anti_overbooking_conflicto(self):
        """Regla R-01: Intentar reservar un bloque ya reservado debe lanzar ReservaConflictError."""
        # Primera reserva exitosa
        ReservaService.reservar_bloque_pesimista(
            bloque_id=self.bloque.id,
            nombre_cliente="Cliente A",
            telefono_cliente="+56911111111",
            email_cliente="clientea@test.cl"
        )

        # Segundo intento sobre el mismo bloque debe fallar
        with self.assertRaises(ReservaConflictError) as ctx:
            ReservaService.reservar_bloque_pesimista(
                bloque_id=self.bloque.id,
                nombre_cliente="Cliente B",
                telefono_cliente="+56922222222",
                email_cliente="clienteb@test.cl"
            )
        self.assertIn("ya fue tomado", str(ctx.exception))

    def test_api_disponibilidad_endpoint(self):
        """Verifica que el endpoint GET /api/disponibilidad/ devuelva los bloques correctos."""
        url = reverse("reservas:api_disponibilidad")
        response = self.client.get(url, {"fecha": self.hoy.isoformat()})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("bloques", response.data)
        self.assertGreaterEqual(len(response.data["bloques"]), 1)

    def test_api_reservar_flujo_y_conflicto_409(self):
        """Verifica el endpoint POST /api/reservar/ para éxito (201) y conflicto (409)."""
        url = reverse("reservas:api_reservar")
        payload = {
            "bloque_id": self.bloque.id,
            "nombre_cliente": "Eliezer Zenteno",
            "telefono_cliente": "+56933334444",
            "email_cliente": "eliezer@test.cl",
            "notas": "Partido final"
        }

        # 1. Petición inicial: 201 Created
        res1 = self.client.post(url, data=payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertIn("reserva", res1.data)
        self.assertIn("email_enmascarado", res1.data["reserva"])

        # 2. Petición duplicada inmediata: 409 Conflict (Prevención de overbooking)
        res2 = self.client.post(url, data=payload, format="json")
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res2.data.get("codigo"), "OVERBOOKING_PREVENTED")


class ConcurrenciaPesimistaMultiThreadTests(TransactionTestCase):
    """
    Test de estrés concurrente multihilo para validar select_for_update() en transacciones reales.
    """
    def setUp(self):
        self.complejo = Complejo.objects.create(nombre="Complejo Multithread Test", direccion="Dir", comuna="Comuna")
        self.superficie = Superficie.objects.create(nombre="Superficie Multithread")
        self.cancha = Cancha.objects.create(
            complejo=self.complejo,
            nombre="Cancha Concurrente",
            superficie=self.superficie,
            precio_base=40000,
            estado='OPERATIVA'
        )
        self.bloque = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=timezone.localdate(),
            hora_inicio=datetime.time(21, 0),
            hora_fin=datetime.time(22, 0),
            precio=40000,
            estado=BloqueHorario.Estado.DISPONIBLE
        )

    def test_concurrencia_simultanea_dos_hilos(self):
        """
        Lanza 2 hilos simultáneos que compiten exactamente por el mismo bloque horario.
        Garantía R-01 (ISO 27034):
        Exactamente 1 hilo debe lograr el arriendo (Éxito) y exactamente 1 debe fallar (Conflicto).
        """
        bloque_id = self.bloque.id
        resultados = []

        def intentar_reserva(nombre, email):
            try:
                res = ConcurrenciaService.reservar_bloque_pesimista(
                    bloque_id=bloque_id,
                    nombre_cliente=nombre,
                    telefono_cliente="+56912345678",
                    email_cliente=email
                )
                return ("OK", res.codigo)
            except ReservaConflictError as e:
                return ("CONFLICT", str(e))
            except Exception as e:
                return ("ERROR", str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(intentar_reserva, "Usuario Alfa", "alfa@test.cl")
            fut2 = executor.submit(intentar_reserva, "Usuario Beta", "beta@test.cl")
            resultados.append(fut1.result())
            resultados.append(fut2.result())

        estados = [r[0] for r in resultados]
        self.assertEqual(estados.count("OK"), 1, f"Debe haber exactamente 1 reserva exitosa. Resultados: {resultados}")
        self.assertEqual(estados.count("CONFLICT"), 1, f"Debe haber exactamente 1 conflicto de concurrencia. Resultados: {resultados}")

        # Comprobar en base de datos que solo existe 1 reserva registrada para este bloque
        reservas_en_bd = Reserva.objects.filter(bloque_id=bloque_id).count()
        self.assertEqual(reservas_en_bd, 1)
