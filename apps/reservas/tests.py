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
        self.assertEqual(
            estados.count("OK"), 1, f"Debe haber exactamente 1 reserva exitosa. Resultados: {resultados}"
        )
        self.assertEqual(
            estados.count("CONFLICT"), 1, f"Debe haber 1 conflicto de concurrencia. Resultados: {resultados}"
        )

        # Comprobar en base de datos que solo existe 1 reserva registrada para este bloque
        reservas_en_bd = Reserva.objects.filter(bloque_id=bloque_id).count()
        self.assertEqual(reservas_en_bd, 1)


class RetroalimentacionDocenteEvaluationTests(TestCase):
    """
    Suite de pruebas automatizadas que valida los 5 puntos exigidos por el profesor:
    1. Reservas funcionales y datos poblados.
    2. Registro/validación obligatoria y separación de perfiles (Cliente vs Admin).
    3. Ventana de tiempo coherente (mínimo 60 min antes, máximo 14 días).
    4. Regla de 1 sola reserva EN_ESPERA por cliente + 3 etapas (En Espera, Aceptada, Denegada) + correo con documento.
    5. Mantenedor de canchas en perfil Admin + registro auditable de cuál Admin modificó últimamente la cancha.
    """
    def setUp(self):
        from django.contrib.auth.models import User
        from apps.reservas.models import PerfilUsuario

        self.client_api = APIClient()
        self.complejo = Complejo.objects.create(
            nombre="Complejo Evaluación",
            direccion="Av. Evaluación 100",
            comuna="Santiago"
        )
        self.superficie = Superficie.objects.create(nombre="Pasto FIFA Pro")
        self.cancha = Cancha.objects.create(
            complejo=self.complejo,
            nombre="Cancha 1 Oficial",
            medidas="45m x 25m (Fútbol 7)",
            superficie=self.superficie,
            precio_base=35000,
            estado="OPERATIVA"
        )
        self.manana = timezone.localdate() + datetime.timedelta(days=1)
        self.bloque_1 = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=self.manana,
            hora_inicio=datetime.time(19, 0),
            hora_fin=datetime.time(20, 0),
            precio=39000,
            es_punta=True,
            estado=BloqueHorario.Estado.DISPONIBLE
        )
        self.bloque_2 = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=self.manana,
            hora_inicio=datetime.time(20, 0),
            hora_fin=datetime.time(21, 0),
            precio=39000,
            es_punta=True,
            estado=BloqueHorario.Estado.DISPONIBLE
        )

        # Crear 2 Administradores
        self.admin_1 = User.objects.create_user(
            username="admin_mario_test",
            email="mario@futbolito7.cl",
            password="AdminPassword123!",
            first_name="Mario",
            last_name="Carrasco",
            is_staff=True
        )
        PerfilUsuario.objects.create(usuario=self.admin_1, rol="ADMIN", cuenta_validada=True)

        self.admin_2 = User.objects.create_user(
            username="admin_eliezer_test",
            email="eliezer@futbolito7.cl",
            password="AdminPassword123!",
            first_name="Eliezer",
            last_name="Zenteno",
            is_staff=True
        )
        PerfilUsuario.objects.create(usuario=self.admin_2, rol="ADMIN", cuenta_validada=True)

        # Crear 1 Cliente Validado
        self.cliente = User.objects.create_user(
            username="paulo_cliente",
            email="paulo.test@yopmail.com",
            password="ClientePassword123!",
            first_name="Paulo",
            last_name="Alegría"
        )
        self.perfil_cliente = PerfilUsuario.objects.create(
            usuario=self.cliente,
            rol="CLIENTE",
            rut="20.123.456-7",
            telefono="+56991234567",
            cuenta_validada=True
        )

    def test_punto_2_separacion_roles_y_registro_obligatorio_en_modo_web(self):
        """Verifica que un anónimo o un Admin no puedan reservar en modo_web, y un Cliente validado sí."""
        url = reverse("reservas:api_reservar")
        payload = {
            "bloque_id": self.bloque_1.id,
            "nombre_cliente": "Paulo Alegría",
            "rut_cliente": "20.123.456-7",
            "telefono_cliente": "+56991234567",
            "email_cliente": "paulo.test@yopmail.com",
            "modo_web": True,
        }

        # 1. Usuario no autenticado -> 401
        res_anon = self.client_api.post(url, data=payload, format="json")
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Usuario con rol ADMIN -> 403 (Separación de perfiles)
        self.client_api.force_authenticate(user=self.admin_1)
        res_admin = self.client_api.post(url, data=payload, format="json")
        self.assertEqual(res_admin.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Usuario CLIENTE validado -> 201 Created en estado EN_ESPERA
        self.client_api.force_authenticate(user=self.cliente)
        res_cli = self.client_api.post(url, data=payload, format="json")
        self.assertEqual(res_cli.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_cli.data["estado_reserva"], Reserva.EstadoReserva.EN_ESPERA)

    def test_punto_3_limite_coherente_ventana_temporal(self):
        """Verifica rechazo de reservas con menos de 60 minutos (ej. 20 min) o más de 14 días (ej. 6 meses)."""
        from apps.reservas.services import VentanaReservaInvalidaError

        ahora = timezone.now()
        # Bloque en 20 minutos más -> Inválido
        en_20_min = ahora + datetime.timedelta(minutes=20)
        bloque_20m = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=timezone.localdate(en_20_min),
            hora_inicio=timezone.localtime(en_20_min).time(),
            hora_fin=(timezone.localtime(en_20_min) + datetime.timedelta(hours=1)).time(),
            precio=35000,
        )
        ok_20m, _ = bloque_20m.validar_ventana_temporal(ahora=ahora)
        self.assertFalse(ok_20m)

        # Bloque en 6 meses (180 días) más -> Inválido
        bloque_6m = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=timezone.localdate(ahora) + datetime.timedelta(days=180),
            hora_inicio=datetime.time(18, 0),
            hora_fin=datetime.time(19, 0),
            precio=35000,
        )
        ok_6m, _ = bloque_6m.validar_ventana_temporal(ahora=ahora)
        self.assertFalse(ok_6m)

        with self.assertRaises(VentanaReservaInvalidaError):
            ReservaService.bloquear_bloque_concurrente(
                bloque_id=bloque_6m.id,
                nombre_cliente="Paulo",
                telefono_cliente="+56991234567",
                email_cliente="paulo.test@yopmail.com",
                usuario=self.cliente,
                validar_ventana=True,
            )

    def test_punto_4_bloqueo_segunda_reserva_y_flujo_3_etapas_con_correo(self):
        """
        Verifica que si el cliente genera una reserva (EN_ESPERA), no puede generar otra hasta que
        el Admin la acepte o la deniegue, y que se envíe correo con documento en cada etapa.
        """
        from django.core import mail
        from apps.reservas.services import ReservaEnEsperaActivaError

        # Etapa 1: Cliente crea primera reserva -> queda EN_ESPERA y envía correo
        r1 = ReservaService.bloquear_bloque_concurrente(
            bloque_id=self.bloque_1.id,
            nombre_cliente="Paulo Alegría",
            telefono_cliente="+56991234567",
            email_cliente="paulo.test@yopmail.com",
            rut_cliente="20.123.456-7",
            usuario=self.cliente,
            validar_ventana=True,
        )
        self.assertEqual(r1.estado_reserva, Reserva.EstadoReserva.EN_ESPERA)
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertIn("EN ESPERA", mail.outbox[-1].subject.upper())

        # Intento de generar una 2da reserva mientras la 1ra está EN_ESPERA -> Bloqueado
        with self.assertRaises(ReservaEnEsperaActivaError):
            ReservaService.bloquear_bloque_concurrente(
                bloque_id=self.bloque_2.id,
                nombre_cliente="Paulo Alegría",
                telefono_cliente="+56991234567",
                email_cliente="paulo.test@yopmail.com",
                usuario=self.cliente,
                validar_ventana=True,
            )

        # Etapa 2B: Admin deniega la primera reserva -> libera bloque y envía correo de DENEGADA
        r1_denegada = ReservaService.resolver_reserva_admin(
            reserva_id=r1.id,
            admin_user=self.admin_1,
            decision="DENEGADA",
            motivo="Mantención eléctrica preventiva",
        )
        self.assertEqual(r1_denegada.estado_reserva, Reserva.EstadoReserva.DENEGADA)
        self.assertEqual(r1_denegada.gestionado_por, self.admin_1)
        self.bloque_1.refresh_from_db()
        self.assertEqual(self.bloque_1.estado, BloqueHorario.Estado.DISPONIBLE)
        self.assertIn("DENEGADA", mail.outbox[-1].subject.upper())

        # Ahora el cliente SÍ puede volver a reservar -> Admin 2 la ACEPTA (Etapa 2A)
        r2 = ReservaService.bloquear_bloque_concurrente(
            bloque_id=self.bloque_2.id,
            nombre_cliente="Paulo Alegría",
            telefono_cliente="+56991234567",
            email_cliente="paulo.test@yopmail.com",
            usuario=self.cliente,
            validar_ventana=True,
        )
        r2_aceptada = ReservaService.resolver_reserva_admin(
            reserva_id=r2.id,
            admin_user=self.admin_2,
            decision="ACEPTADA",
            motivo="Pago y horario verificados",
        )
        self.assertEqual(r2_aceptada.estado_reserva, Reserva.EstadoReserva.ACEPTADA)
        self.assertEqual(r2_aceptada.gestionado_por, self.admin_2)
        self.bloque_2.refresh_from_db()
        self.assertEqual(self.bloque_2.estado, BloqueHorario.Estado.RESERVADO)
        self.assertIn("ACEPTADA", mail.outbox[-1].subject.upper())

    def test_punto_5_mantenedor_cancha_y_auditoria_dos_admins(self):
        """
        Verifica que el editor de cancha actualice nombre, medidas y estado, y registre
        cuál de los 2 administradores modificó últimamente la cancha.
        """
        from apps.canchas.models import HistorialModificacionCancha

        url_editar = reverse("reservas:admin_editar_cancha", args=[self.cancha.id])

        # Admin 1 (Mario) modifica nombre y medidas
        self.client.force_login(self.admin_1)
        self.client.post(url_editar, {
            "nombre": "Cancha 1 - Estadio Monumental Pro",
            "medidas": "50m x 30m (Fútbol 7 Pro)",
            "superficie_id": self.superficie.id,
            "precio_base": 40000,
            "estado": "OPERATIVA",
            "techada": "on",
            "iluminacion_led": "on",
        })
        self.cancha.refresh_from_db()
        self.assertEqual(self.cancha.nombre, "Cancha 1 - Estadio Monumental Pro")
        self.assertEqual(self.cancha.medidas, "50m x 30m (Fútbol 7 Pro)")
        self.assertEqual(self.cancha.modificado_por, self.admin_1)

        # Admin 2 (Eliezer) modifica precio y medidas posteriormente
        self.client.force_login(self.admin_2)
        self.client.post(url_editar, {
            "nombre": "Cancha 1 - Estadio Monumental Pro",
            "medidas": "48m x 28m (Fútbol 7 Oficial)",
            "superficie_id": self.superficie.id,
            "precio_base": 44000,
            "estado": "OPERATIVA",
            "techada": "on",
            "iluminacion_led": "on",
        })
        self.cancha.refresh_from_db()
        self.assertEqual(self.cancha.medidas, "48m x 28m (Fútbol 7 Oficial)")
        self.assertEqual(self.cancha.modificado_por, self.admin_2)

        # El historial registra ambas modificaciones con su respectivo administrador
        historial = HistorialModificacionCancha.objects.filter(cancha=self.cancha).order_by("fecha")
        self.assertEqual(historial.count(), 2)
        self.assertEqual(historial[0].administrador, self.admin_1)
        self.assertEqual(historial[1].administrador, self.admin_2)
