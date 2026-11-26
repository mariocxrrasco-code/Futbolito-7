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
        """Verifica el endpoint POST /api/reservar/ autenticado para éxito (201) y conflicto (409)."""
        from django.contrib.auth.models import User
        from apps.reservas.models import PerfilUsuario

        manana = timezone.localdate() + datetime.timedelta(days=1)
        bloque_futuro = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=manana,
            hora_inicio=datetime.time(19, 0),
            hora_fin=datetime.time(20, 0),
            precio=36000,
            es_punta=True,
            estado=BloqueHorario.Estado.DISPONIBLE,
        )

        cli_1 = User.objects.create_user(
            username="eliezer_cli",
            email="eliezer@test.cl",
            password="PasswordSegura1!",
            first_name="Eliezer",
            last_name="Zenteno",
        )
        PerfilUsuario.objects.create(
            usuario=cli_1, rol="CLIENTE", rut="20.111.222-3", telefono="+56933334444", cuenta_validada=True
        )

        cli_2 = User.objects.create_user(
            username="segundo_cli",
            email="segundo@test.cl",
            password="PasswordSegura1!",
            first_name="Segundo",
            last_name="Jugador",
        )
        PerfilUsuario.objects.create(
            usuario=cli_2, rol="CLIENTE", rut="20.444.555-6", telefono="+56955556666", cuenta_validada=True
        )

        url = reverse("reservas:api_reservar")
        payload = {
            "bloque_id": bloque_futuro.id,
            "notas": "Partido final"
        }

        # 1. Petición inicial autenticada como Cliente 1: 201 Created
        self.client.force_authenticate(user=cli_1)
        res1 = self.client.post(url, data=payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertIn("reserva", res1.data)
        self.assertIn("email_enmascarado", res1.data["reserva"])

        # 2. Petición de Cliente 2 sobre el mismo bloque: 409 Conflict (Prevención de overbooking)
        self.client.force_authenticate(user=cli_2)
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

    def test_saneamiento_backend_login_contra_inyeccion_burpsuite(self):
        """
        Verifica que incluso si se intercepta el POST de /login/ (ej. con Burp Suite Proxy)
        para inyectar SQLi o XSS, el backend lo bloquea antes de consultar la BD.
        """
        url_login = reverse("reservas:login")
        payloads_maliciosos = [
            "' OR '1'='1",
            "admin'--",
            "<script>alert(1)</script>",
            "mario@futbolito7.cl; DROP TABLE auth_user;--",
        ]
        for payload in payloads_maliciosos:
            resp = self.client.post(url_login, {
                "username": payload,
                "password": "CualquierPassword1!",
            })
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(resp.wsgi_request.user.is_authenticated)
            self.assertContains(resp, "Entrada bloqueada por seguridad")

        # Un usuario legítimo válido (por username o email) sigue funcionando sin problema
        resp_ok = self.client.post(url_login, {
            "username": "paulo_cliente",
            "password": "ClientePassword123!",
        })
        self.assertEqual(resp_ok.status_code, 302)
        self.assertTrue(resp_ok.wsgi_request.user.is_authenticated)


class AuditoriaSeguridadOWASPTests(TestCase):
    """
    Suite de blindaje OWASP Top 10 / ISO 27034 para auditoría cruzada de URL en producción.
    """
    def setUp(self):
        from django.contrib.auth.models import User
        from django.core.cache import cache
        from apps.reservas.models import PerfilUsuario

        cache.clear()
        self.api = APIClient()
        self.complejo = Complejo.objects.create(
            nombre="Complejo Auditado",
            direccion="Av. Seguridad 100",
            comuna="Concepción"
        )
        self.superficie = Superficie.objects.create(nombre="Césped FIFA Audit")
        self.cancha = Cancha.objects.create(
            complejo=self.complejo,
            nombre="Cancha Blindada 1",
            superficie=self.superficie,
            precio_base=30000,
            estado="OPERATIVA"
        )
        self.manana = timezone.localdate() + datetime.timedelta(days=1)
        self.bloque = BloqueHorario.objects.create(
            cancha=self.cancha,
            fecha=self.manana,
            hora_inicio=datetime.time(20, 0),
            hora_fin=datetime.time(21, 0),
            precio=30000,
            es_punta=True,
            estado=BloqueHorario.Estado.DISPONIBLE
        )

        self.admin = User.objects.create_user(
            username="admin_audit",
            email="admin_audit@futbolito7.cl",
            password="AdminPassword123!",
            is_staff=True
        )
        self.perfil_admin = PerfilUsuario.objects.create(
            usuario=self.admin, rol="ADMIN", cuenta_validada=True
        )

        self.cliente_a = User.objects.create_user(
            username="cliente_a",
            email="cliente_a@yopmail.com",
            password="ClientePassword123!",
            first_name="Cliente",
            last_name="Alfa"
        )
        self.perfil_a = PerfilUsuario.objects.create(
            usuario=self.cliente_a,
            rol="CLIENTE",
            rut="20.111.111-1",
            telefono="+56 9 1111 1111",
            cuenta_validada=True
        )

        self.cliente_b = User.objects.create_user(
            username="cliente_b",
            email="cliente_b@yopmail.com",
            password="ClientePassword123!",
            first_name="Cliente",
            last_name="Beta"
        )
        self.perfil_b = PerfilUsuario.objects.create(
            usuario=self.cliente_b,
            rol="CLIENTE",
            rut="20.222.222-2",
            telefono="+56 9 2222 2222",
            cuenta_validada=True
        )

    def test_cabeceras_seguridad_http_y_cache_control(self):
        """OWASP A05: Verifica CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy y Cache-Control."""
        resp_home = self.client.get(reverse("reservas:grilla"))
        self.assertEqual(resp_home.status_code, 200)
        self.assertIn("Content-Security-Policy", resp_home)
        self.assertIn("frame-ancestors 'none'", resp_home["Content-Security-Policy"])
        self.assertEqual(resp_home["X-Frame-Options"], "DENY")
        self.assertEqual(resp_home["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp_home["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("Permissions-Policy", resp_home)
        self.assertEqual(resp_home["Cross-Origin-Opener-Policy"], "same-origin")

        resp_login = self.client.get(reverse("reservas:login"))
        self.assertIn("no-store", resp_login["Cache-Control"])

    def test_api_reservar_sin_bypass_modo_web_ni_suplantacion(self):
        """OWASP A01 / A04: Impide bypass anónimo con modo_web=False, bloqueo a Admin y suplantación de identidad."""
        url = reverse("reservas:api_reservar")
        payload_bypass = {
            "bloque_id": self.bloque.id,
            "modo_web": False,
            "nombre_cliente": "Atacante Anónimo",
            "email_cliente": "atacante@evil.cl",
            "telefono_cliente": "+56900000000",
            "rut_cliente": "11.111.111-1",
        }

        # Anónimo intentando bypass con modo_web=False -> 401
        resp_anon = self.api.post(url, data=payload_bypass, format="json")
        self.assertEqual(resp_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # Admin intentando bypass con modo_web=False -> 403
        self.api.force_authenticate(user=self.admin)
        resp_admin = self.api.post(url, data=payload_bypass, format="json")
        self.assertEqual(resp_admin.status_code, status.HTTP_403_FORBIDDEN)

        # Cliente autenticado intentando suplantar datos de otro usuario -> backend ignora payload y usa su perfil real
        self.api.force_authenticate(user=self.cliente_a)
        resp_cli = self.api.post(url, data=payload_bypass, format="json")
        self.assertEqual(resp_cli.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_cli.data["estado_reserva"], Reserva.EstadoReserva.EN_ESPERA)
        self.assertEqual(resp_cli.data["nombre_cliente"], "Cliente Alfa")
        self.assertEqual(resp_cli.data["reserva"]["rut_cliente"], "20.111.111-1")

    def test_api_test_concurrencia_restringida_a_admin(self):
        """OWASP A01: Impide DoS anónimo o de clientes sobre /api/test-concurrencia/."""
        url = reverse("reservas:api_test_concurrencia")
        self.assertEqual(self.api.post(url).status_code, status.HTTP_401_UNAUTHORIZED)

        self.api.force_authenticate(user=self.cliente_a)
        self.assertEqual(self.api.post(url).status_code, status.HTTP_403_FORBIDDEN)

        self.api.force_authenticate(user=self.admin)
        self.assertEqual(self.api.post(url).status_code, status.HTTP_200_OK)

    def test_comprobante_proteccion_anti_idor(self):
        """OWASP A01 (IDOR): Solo el dueño de la reserva o un Admin pueden ver /comprobante/<uuid>/."""
        reserva = ReservaService.bloquear_bloque_concurrente(
            bloque_id=self.bloque.id,
            usuario=self.cliente_a,
            rut_cliente="20.111.111-1",
            nombre_cliente="Cliente Alfa",
            telefono_cliente="+56 9 1111 1111",
            email_cliente="cliente_a@yopmail.com",
            validar_ventana=True,
        )
        url = reverse("reservas:comprobante", args=[reserva.codigo])

        # Anónimo -> redirige a login
        resp_anon = self.client.get(url)
        self.assertEqual(resp_anon.status_code, 302)
        self.assertIn("/login/", resp_anon.url)

        # Otro cliente (IDOR) -> 403 Forbidden
        self.client.force_login(self.cliente_b)
        resp_idor = self.client.get(url)
        self.assertEqual(resp_idor.status_code, 403)

        # Titular legítimo -> 200 OK
        self.client.force_login(self.cliente_a)
        self.assertEqual(self.client.get(url).status_code, 200)

        # Administrador -> 200 OK
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_token_validacion_unico_uso_y_bloqueo_suspendido(self):
        """OWASP A07: El enlace de validación rota el token (1 solo uso) y bloquea cuentas suspendidas."""
        from django.contrib.auth.models import User
        from apps.reservas.models import PerfilUsuario

        user_nuevo = User.objects.create_user(
            username="nuevo_token", email="nuevo@yopmail.com", password="Password123!"
        )
        perfil = PerfilUsuario.objects.create(
            usuario=user_nuevo, rol="CLIENTE", cuenta_validada=False, suspendido=False
        )
        token_inicial = perfil.token_validacion
        url_validar = reverse("reservas:validar_cuenta", args=[token_inicial])

        # Primer uso válido -> activa y rota token
        resp1 = self.client.get(url_validar)
        self.assertEqual(resp1.status_code, 302)
        perfil.refresh_from_db()
        self.assertTrue(perfil.cuenta_validada)
        self.assertNotEqual(perfil.token_validacion, token_inicial)

        # Reutilización del mismo enlace -> 404 (no sirve como puerta trasera sin contraseña)
        self.client.logout()
        resp2 = self.client.get(url_validar)
        self.assertEqual(resp2.status_code, 404)

        # Cuenta suspendida no puede auto-loguearse por token
        perfil.cuenta_validada = False
        perfil.suspendido = True
        perfil.save()
        url_susp = reverse("reservas:validar_cuenta", args=[perfil.token_validacion])
        resp_susp = self.client.get(url_susp)
        self.assertEqual(resp_susp.status_code, 302)
        self.assertFalse(resp_susp.wsgi_request.user.is_authenticated)

    def test_logout_requiere_post_y_rechaza_get(self):
        """OWASP A01 (Logout CSRF): GET /logout/ debe responder 405 sin cerrar sesión; POST sí cierra."""
        self.client.force_login(self.cliente_a)
        resp_get = self.client.get(reverse("reservas:logout"))
        self.assertEqual(resp_get.status_code, 405)
        self.assertTrue(self.client.session.get("_auth_user_id"))

        resp_post = self.client.post(reverse("reservas:logout"))
        self.assertEqual(resp_post.status_code, 302)
        self.assertFalse(self.client.session.get("_auth_user_id"))

    def test_rate_limit_fuerza_bruta_login_y_open_redirect(self):
        """OWASP A07 / A01: Bloquea fuerza bruta con HTTP 429 y rechaza Open Redirect en ?next=."""
        url_login = reverse("reservas:login")
        for _ in range(5):
            r = self.client.post(url_login, {"username": "cliente_a", "password": "WrongPassword1!"})
            self.assertEqual(r.status_code, 200)

        # 6to intento bloqueado con 429 Too Many Requests
        r_bloqueado = self.client.post(url_login, {"username": "cliente_a", "password": "ClientePassword123!"})
        self.assertEqual(r_bloqueado.status_code, 429)

        # Open Redirect bloqueado para otro usuario no bloqueado
        r_redir = self.client.post(
            url_login,
            {
                "username": "cliente_b",
                "password": "ClientePassword123!",
                "next": "https://evil.example.com/phishing",
            },
        )
        self.assertEqual(r_redir.status_code, 302)
        self.assertFalse(r_redir.url.startswith("https://evil.example.com"))

    def test_admin_inputs_malformados_sin_500_y_proteccion_cuentas_admin(self):
        """OWASP A03 / A01: Inputs extremos en Admin no causan HTTP 500 y no se puede suspender un Admin."""
        self.client.force_login(self.admin)
        url_editar = reverse("reservas:admin_editar_cancha", args=[self.cancha.id])

        # superficie_id no numérico y precio negativo/NaN -> redirige con alerta, nunca 500
        for bad_data in [
            {"superficie_id": "abc", "precio_base": "30000"},
            {"superficie_id": str(self.superficie.id), "precio_base": "-50000"},
            {"superficie_id": str(self.superficie.id), "precio_base": "NaN"},
            {"nombre": "A" * 150, "medidas": "40x20"},
        ]:
            resp = self.client.post(url_editar, bad_data)
            self.assertEqual(resp.status_code, 302)

        # Intentar suspender perfil Admin -> 403 Forbidden
        url_gestionar = reverse("reservas:admin_gestionar_jugador", args=[self.perfil_admin.id])
        resp_susp_admin = self.client.post(url_gestionar, {"accion": "toggle_suspension"})
        self.assertEqual(resp_susp_admin.status_code, 403)
        self.perfil_admin.refresh_from_db()
        self.assertFalse(self.perfil_admin.suspendido)

    def test_reserva_web_con_csrf_enforced_y_meta_token(self):
        """Rúbrica EV4 (Criterios 5 y 7): Verifica POST /api/reservar/ y POST /logout/ con CSRF estricto."""
        import json
        import re
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        # 1. Login vía POST con CSRF real
        get_login = csrf_client.get(reverse("reservas:login"))
        match_csrf = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', get_login.content.decode())
        self.assertIsNotNone(match_csrf)
        resp_login = csrf_client.post(
            reverse("reservas:login"),
            {
                "csrfmiddlewaretoken": match_csrf.group(1),
                "username": "cliente_a",
                "password": "ClientePassword123!",
            },
        )
        self.assertEqual(resp_login.status_code, 302)

        # 2. Leer <meta name="csrf-token"> desde / (funciona incluso con CSRF_COOKIE_HTTPONLY=True)
        get_home = csrf_client.get(reverse("reservas:grilla"))
        self.assertEqual(get_home.status_code, 200)
        self.assertIn("no-store", get_home["Cache-Control"])
        match_meta = re.search(r'<meta name="csrf-token" content="([^"]+)"/>', get_home.content.decode())
        self.assertIsNotNone(match_meta)
        csrf_token = match_meta.group(1)

        # 3. Sin header X-CSRFToken -> 403 Forbidden
        url_reservar = reverse("reservas:api_reservar")
        resp_sin_csrf = csrf_client.post(
            url_reservar,
            data=json.dumps({"bloque_id": self.bloque.id, "notas": "Sin token"}),
            content_type="application/json",
        )
        self.assertEqual(resp_sin_csrf.status_code, 403)

        # 4. Con header X-CSRFToken leído del meta -> 201 Created
        resp_con_csrf = csrf_client.post(
            url_reservar,
            data=json.dumps({"bloque_id": self.bloque.id, "notas": "Partido auditado"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(resp_con_csrf.status_code, 201)

        # 5. Logout con POST + CSRF y verificar que vista privada vuelve a pedir login
        resp_logout = csrf_client.post(
            reverse("reservas:logout"),
            {"csrfmiddlewaretoken": csrf_token},
        )
        self.assertEqual(resp_logout.status_code, 302)
        resp_priv = csrf_client.get(reverse("reservas:mis_reservas"))
        self.assertEqual(resp_priv.status_code, 302)
        self.assertIn("/login/", resp_priv.url)
