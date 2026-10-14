import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.canchas.models import Complejo, Superficie, Cancha, Tarifa
from apps.reservas.models import BloqueHorario, Reserva


class Command(BaseCommand):
    help = "Puebla la base de datos con datos realistas para la demostración de Futbolito 7"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando seed de datos para Futbolito 7..."))

        # 1. Complejo
        complejo, _ = Complejo.objects.get_or_create(
            nombre="Complejo Deportivo Futbolito 7 Central",
            defaults={
                "direccion": "Av. Américo Vespucio Sur 1500",
                "comuna": "Santiago",
                "telefono": "+56 9 8765 4321",
                "email": "contacto@futbolito7.cl",
                "activo": True
            }
        )

        # 2. Superficies
        sup_fifa, _ = Superficie.objects.get_or_create(
            nombre="Pasto Sintético FIFA Pro",
            defaults={"descripcion": "Fibra de monofilamento con relleno de caucho criogénico ecológico."}
        )
        sup_techada, _ = Superficie.objects.get_or_create(
            nombre="Césped Sintético Techado Alta Resistencia",
            defaults={"descripcion": "Pabellón cubierto con ventilación y amortiguación de impacto."}
        )
        sup_rapida, _ = Superficie.objects.get_or_create(
            nombre="Césped Exterior Clásico",
            defaults={"descripcion": "Cancha descubierta para fútbol 7 tradicional con césped 50mm."}
        )

        # 3. Canchas
        canchas_data = [
            {
                "nombre": "Cancha 1 - Monumental Techada",
                "superficie": sup_techada,
                "techada": True,
                "iluminacion_led": True,
                "precio_base": 38000,
            },
            {
                "nombre": "Cancha 2 - Bombonera Exterior",
                "superficie": sup_fifa,
                "techada": False,
                "iluminacion_led": True,
                "precio_base": 32000,
            },
            {
                "nombre": "Cancha 3 - Maracaná Pro",
                "superficie": sup_fifa,
                "techada": True,
                "iluminacion_led": True,
                "precio_base": 42000,
            },
        ]

        canchas_creadas = []
        for cdata in canchas_data:
            cancha, _ = Cancha.objects.get_or_create(
                complejo=complejo,
                nombre=cdata["nombre"],
                defaults=cdata
            )
            canchas_creadas.append(cancha)

        # 4. Tarifas Diferenciadas (Valle vs Punta)
        for cancha in canchas_creadas:
            for dia in range(7):
                es_finde = dia in [5, 6]
                if not es_finde:
                    # Lunes a Viernes Valle (09:00 - 17:00)
                    Tarifa.objects.get_or_create(
                        cancha=cancha,
                        dia_semana=dia,
                        hora_inicio=datetime.time(9, 0),
                        hora_fin=datetime.time(17, 0),
                        defaults={
                            "tipo_horario": Tarifa.TipoHorario.VALLE,
                            "precio_bloque": cancha.precio_base - 8000
                        }
                    )
                    # Lunes a Viernes Punta (18:00 - 23:00)
                    Tarifa.objects.get_or_create(
                        cancha=cancha,
                        dia_semana=dia,
                        hora_inicio=datetime.time(18, 0),
                        hora_fin=datetime.time(23, 0),
                        defaults={
                            "tipo_horario": Tarifa.TipoHorario.PUNTA,
                            "precio_bloque": cancha.precio_base + 4000
                        }
                    )
                else:
                    # Sábado y Domingo todo el día es Punta
                    Tarifa.objects.get_or_create(
                        cancha=cancha,
                        dia_semana=dia,
                        hora_inicio=datetime.time(9, 0),
                        hora_fin=datetime.time(23, 0),
                        defaults={
                            "tipo_horario": Tarifa.TipoHorario.PUNTA,
                            "precio_bloque": cancha.precio_base + 6000
                        }
                    )

        # 5. Generar Bloques Horarios para los próximos 5 días
        hoy = timezone.localdate()
        horas = [
            (datetime.time(9, 0), datetime.time(10, 0)),
            (datetime.time(10, 0), datetime.time(11, 0)),
            (datetime.time(11, 0), datetime.time(12, 0)),
            (datetime.time(12, 0), datetime.time(13, 0)),
            (datetime.time(13, 0), datetime.time(14, 0)),
            (datetime.time(14, 0), datetime.time(15, 0)),
            (datetime.time(15, 0), datetime.time(16, 0)),
            (datetime.time(16, 0), datetime.time(17, 0)),
            (datetime.time(17, 0), datetime.time(18, 0)),
            (datetime.time(18, 0), datetime.time(19, 0)),
            (datetime.time(19, 0), datetime.time(20, 0)),
            (datetime.time(20, 0), datetime.time(21, 0)),
            (datetime.time(21, 0), datetime.time(22, 0)),
            (datetime.time(22, 0), datetime.time(23, 0)),
        ]

        bloques_count = 0
        for offset in range(5):
            fecha = hoy + datetime.timedelta(days=offset)
            dia_sem = fecha.weekday()
            es_finde = dia_sem in [5, 6]

            for cancha in canchas_creadas:
                for h_ini, h_fin in horas:
                    # Determinar si es punta
                    es_punta = es_finde or (h_ini.hour >= 18)
                    precio = (cancha.precio_base + 4000) if es_punta else (cancha.precio_base - 8000)

                    bloque, created = BloqueHorario.objects.get_or_create(
                        cancha=cancha,
                        fecha=fecha,
                        hora_inicio=h_ini,
                        defaults={
                            "hora_fin": h_fin,
                            "precio": precio,
                            "es_punta": es_punta,
                            "estado": BloqueHorario.Estado.DISPONIBLE
                        }
                    )
                    if created:
                        bloques_count += 1

        # Crear un par de reservas de demostración
        bloque_demo = BloqueHorario.objects.filter(
            fecha=hoy,
            hora_inicio=datetime.time(20, 0),
            estado=BloqueHorario.Estado.DISPONIBLE
        ).first()

        if bloque_demo:
            bloque_demo.estado = BloqueHorario.Estado.RESERVADO
            bloque_demo.save()
            Reserva.objects.get_or_create(
                bloque=bloque_demo,
                defaults={
                    "nombre_cliente": "Rodrigo Morales",
                    "telefono_cliente": "+56991234567",
                    "email_cliente": "rmorales@gmail.com",
                    "estado_pago": Reserva.EstadoPago.PAGADO,
                    "monto_total": bloque_demo.precio,
                    "notas": "Partido semanal liga nocturna"
                }
            )

        self.stdout.write(self.style.SUCCESS(f"Seed completado exitosamente: {bloques_count} bloques horarios generados."))
