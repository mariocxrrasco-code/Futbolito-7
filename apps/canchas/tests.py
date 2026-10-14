import datetime
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status
from apps.canchas.models import Complejo, Superficie, Cancha, Tarifa


class CanchasModelAndApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.complejo = Complejo.objects.create(
            nombre="Complejo Test Pro",
            direccion="Calle Falsa 123",
            comuna="Providencia",
            telefono="+56911223344",
            email="test@futbolito7.cl",
            activo=True
        )
        self.superficie = Superficie.objects.create(
            nombre="Césped Sintético Test",
            descripcion="Superficie para pruebas unitarias"
        )
        self.cancha = Cancha.objects.create(
            complejo=self.complejo,
            nombre="Cancha 1 Test",
            superficie=self.superficie,
            techada=True,
            iluminacion_led=True,
            precio_base=35000,
            estado='OPERATIVA',
            activa=True
        )
        self.tarifa_valle = Tarifa.objects.create(
            cancha=self.cancha,
            tipo_horario=Tarifa.TipoHorario.VALLE,
            dia_semana=0,
            hora_inicio=datetime.time(9, 0),
            hora_fin=datetime.time(17, 0),
            precio_bloque=27000
        )

    def test_creacion_complejo_y_cancha(self):
        """Verifica la correcta instanciación de los modelos de complejos y canchas."""
        self.assertEqual(str(self.complejo), "Complejo Test Pro (Providencia)")
        self.assertEqual(str(self.cancha), "Cancha 1 Test - Complejo Test Pro")
        self.assertTrue(self.cancha.techada)
        self.assertEqual(self.cancha.precio_base, 35000)
        self.assertEqual(self.cancha.estado, 'OPERATIVA')

    def test_tarifa_y_str(self):
        """Verifica el cálculo y representación en string de la tarifa horaria."""
        self.assertIn("Lunes", str(self.tarifa_valle))
        self.assertIn(f"{self.tarifa_valle.precio_bloque:,.0f}", str(self.tarifa_valle))
        self.assertEqual(self.tarifa_valle.tipo_horario, Tarifa.TipoHorario.VALLE)

    def test_regla_r03_maximo_40_porciento_mantencion(self):
        """
        CONTROL R-03 (ISO 27034):
        Verifica que no se permita superar el 40% de canchas en mantención en un complejo.
        """
        # Crear 4 canchas en total en el complejo (Cancha 1 ya creada)
        cancha2 = Cancha.objects.create(
            complejo=self.complejo, nombre="Cancha 2 Test", superficie=self.superficie,
            precio_base=35000, estado='OPERATIVA'
        )
        cancha3 = Cancha.objects.create(
            complejo=self.complejo, nombre="Cancha 3 Test", superficie=self.superficie,
            precio_base=35000, estado='OPERATIVA'
        )
        cancha4 = Cancha.objects.create(
            complejo=self.complejo, nombre="Cancha 4 Test", superficie=self.superficie,
            precio_base=35000, estado='OPERATIVA'
        )

        # 1/4 canchas fuera = 25% (Permitido <= 40%)
        cancha2.estado = 'MANTENCION'
        cancha2.save()
        self.assertEqual(cancha2.estado, 'MANTENCION')

        # 2/4 canchas fuera = 50% (Prohibido > 40%) -> Debe lanzar ValidationError
        cancha3.estado = 'MANTENCION'
        with self.assertRaises(ValidationError) as ctx:
            cancha3.clean()

        self.assertIn("Infracción Operacional", str(ctx.exception))
        self.assertIn("Máximo permitido: 40%", str(ctx.exception))

    def test_api_list_canchas(self):
        """Verifica el endpoint GET /canchas/api/canchas/."""
        url = reverse("canchas:api_canchas_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["nombre"], "Cancha 1 Test")
        self.assertEqual(response.data[0]["complejo_nombre"], "Complejo Test Pro")
