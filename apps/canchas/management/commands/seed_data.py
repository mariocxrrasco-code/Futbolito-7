import datetime
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.canchas.models import Complejo, Superficie, Cancha, Tarifa, HistorialModificacionCancha
from apps.reservas.models import BloqueHorario, Reserva, PerfilUsuario


class Command(BaseCommand):
    help = "Puebla la base de datos con complejo, 4 canchas, 2 administradores, clientes validados y bloques horarios"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando seed de datos para Futbolito 7..."))

        # 1. Cuentas de Administrador (2 Admins para demostrar auditoría de quién modificó cada cancha)
        admin_mario, created_m = User.objects.get_or_create(
            username="admin_mario",
            defaults={
                "email": "mario@futbolito7.cl",
                "first_name": "Mario",
                "last_name": "Carrasco (Admin)",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_mario.email = "mario@futbolito7.cl"
        admin_mario.first_name = "Mario"
        admin_mario.last_name = "Carrasco (Admin)"
        admin_mario.is_staff = True
        admin_mario.is_superuser = True
        admin_mario.set_password("Admin2026!")
        admin_mario.save()
        PerfilUsuario.objects.update_or_create(
            usuario=admin_mario,
            defaults={
                "rol": PerfilUsuario.Rol.ADMIN,
                "rut": "19.111.222-3",
                "telefono": "+56 9 8111 2233",
                "cuenta_validada": True,
            },
        )

        admin_eliezer, created_e = User.objects.get_or_create(
            username="admin_eliezer",
            defaults={
                "email": "eliezer@futbolito7.cl",
                "first_name": "Eliezer",
                "last_name": "Zenteno (Admin)",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_eliezer.email = "eliezer@futbolito7.cl"
        admin_eliezer.first_name = "Eliezer"
        admin_eliezer.last_name = "Zenteno (Admin)"
        admin_eliezer.is_staff = True
        admin_eliezer.is_superuser = True
        admin_eliezer.set_password("Admin2026!")
        admin_eliezer.save()
        PerfilUsuario.objects.update_or_create(
            usuario=admin_eliezer,
            defaults={
                "rol": PerfilUsuario.Rol.ADMIN,
                "rut": "18.444.555-6",
                "telefono": "+56 9 8444 5566",
                "cuenta_validada": True,
            },
        )

        # 2. Cuentas de Clientes Validados (Con correos Yopmail para pruebas de notificación)
        cliente_paulo, created_p = User.objects.get_or_create(
            username="cliente_paulo",
            defaults={
                "email": "paulo.futbolito7@yopmail.com",
                "first_name": "Paulo",
                "last_name": "Alegría",
                "is_staff": False,
            },
        )
        cliente_paulo.email = "paulo.futbolito7@yopmail.com"
        cliente_paulo.first_name = "Paulo"
        cliente_paulo.last_name = "Alegría"
        cliente_paulo.set_password("Cliente2026!")
        cliente_paulo.save()
        PerfilUsuario.objects.update_or_create(
            usuario=cliente_paulo,
            defaults={
                "rol": PerfilUsuario.Rol.CLIENTE,
                "rut": "20.123.456-7",
                "telefono": "+56 9 9123 4567",
                "cuenta_validada": True,
            },
        )

        cliente_ivan, created_i = User.objects.get_or_create(
            username="cliente_ivan",
            defaults={
                "email": "ivan.futbolito7@yopmail.com",
                "first_name": "Iván",
                "last_name": "Alejandro",
                "is_staff": False,
            },
        )
        cliente_ivan.email = "ivan.futbolito7@yopmail.com"
        cliente_ivan.first_name = "Iván"
        cliente_ivan.last_name = "Alejandro"
        cliente_ivan.set_password("Cliente2026!")
        cliente_ivan.save()
        PerfilUsuario.objects.update_or_create(
            usuario=cliente_ivan,
            defaults={
                "rol": PerfilUsuario.Rol.CLIENTE,
                "rut": "20.987.654-K",
                "telefono": "+56 9 9876 5432",
                "cuenta_validada": True,
            },
        )

        # 3. Complejo Deportivo
        complejo, _ = Complejo.objects.update_or_create(
            nombre="Complejo Deportivo Futbolito 7 Central",
            defaults={
                "direccion": "Av. Paicaví 2580",
                "comuna": "Concepción",
                "telefono": "+56 9 8765 4321",
                "email": "contacto@futbolito7.cl",
                "activo": True,
            },
        )

        # 4. Superficies
        sup_fifa, _ = Superficie.objects.get_or_create(
            nombre="Pasto Sintético FIFA Pro",
            defaults={"descripcion": "Fibra de monofilamento con relleno de caucho criogénico ecológico."},
        )
        sup_techada, _ = Superficie.objects.get_or_create(
            nombre="Césped Sintético Techado Alta Resistencia",
            defaults={"descripcion": "Pabellón cubierto con ventilación y amortiguación de impacto."},
        )
        sup_rapida, _ = Superficie.objects.get_or_create(
            nombre="Césped Exterior Clásico 50mm",
            defaults={"descripcion": "Cancha descubierta para fútbol 7 tradicional con césped 50mm."},
        )

        # 5. Canchas (4 canchas para cumplir regla R-03 y mostrar quién modificó cada una)
        canchas_data = [
            {
                "nombre": "Cancha 1 - Monumental Techada",
                "medidas": "45m x 25m (Fútbol 7 Reglamentaria)",
                "superficie": sup_techada,
                "techada": True,
                "iluminacion_led": True,
                "precio_base": 38000,
                "modificado_por": admin_mario,
                "fecha_modificacion": timezone.now(),
            },
            {
                "nombre": "Cancha 2 - Bombonera Exterior",
                "medidas": "42m x 24m (Fútbol 7 Estándar)",
                "superficie": sup_fifa,
                "techada": False,
                "iluminacion_led": True,
                "precio_base": 32000,
                "modificado_por": admin_eliezer,
                "fecha_modificacion": timezone.now(),
            },
            {
                "nombre": "Cancha 3 - Maracaná Pro",
                "medidas": "50m x 30m (Fútbol 7 Pro Liga)",
                "superficie": sup_fifa,
                "techada": True,
                "iluminacion_led": True,
                "precio_base": 42000,
                "modificado_por": admin_mario,
                "fecha_modificacion": timezone.now(),
            },
            {
                "nombre": "Cancha 4 - Wembley Sur",
                "medidas": "40m x 22m (Fútbol 7 Rápido)",
                "superficie": sup_rapida,
                "techada": False,
                "iluminacion_led": True,
                "precio_base": 30000,
                "modificado_por": admin_eliezer,
                "fecha_modificacion": timezone.now(),
            },
        ]

        canchas_creadas = []
        for cdata in canchas_data:
            cancha, created_c = Cancha.objects.update_or_create(
                complejo=complejo,
                nombre=cdata["nombre"],
                defaults=cdata,
            )
            canchas_creadas.append(cancha)
            if created_c or not cancha.historial_modificaciones.exists():
                HistorialModificacionCancha.objects.create(
                    cancha=cancha,
                    administrador=cdata["modificado_por"],
                    detalle_cambio=(
                        f"Configuración de cancha verificada: Medidas='{cdata['medidas']}', "
                        f"Precio base=${cdata['precio_base']:,} CLP, Estado=OPERATIVA."
                    ),
                )

        # 6. Tarifas Diferenciadas (Valle vs Punta)
        for cancha in canchas_creadas:
            for dia in range(7):
                es_finde = dia in [5, 6]
                if not es_finde:
                    Tarifa.objects.get_or_create(
                        cancha=cancha,
                        dia_semana=dia,
                        hora_inicio=datetime.time(9, 0),
                        hora_fin=datetime.time(17, 0),
                        defaults={
                            "tipo_horario": Tarifa.TipoHorario.VALLE,
                            "precio_bloque": cancha.precio_base - 8000,
                        },
                    )
                    Tarifa.objects.get_or_create(
                        cancha=cancha,
                        dia_semana=dia,
                        hora_inicio=datetime.time(18, 0),
                        hora_fin=datetime.time(23, 0),
                        defaults={
                            "tipo_horario": Tarifa.TipoHorario.PUNTA,
                            "precio_bloque": cancha.precio_base + 4000,
                        },
                    )
                else:
                    Tarifa.objects.get_or_create(
                        cancha=cancha,
                        dia_semana=dia,
                        hora_inicio=datetime.time(9, 0),
                        hora_fin=datetime.time(23, 0),
                        defaults={
                            "tipo_horario": Tarifa.TipoHorario.PUNTA,
                            "precio_bloque": cancha.precio_base + 6000,
                        },
                    )

        # 7. Generar Bloques Horarios para los próximos 7 días (dentro del límite coherente de 14 días)
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
        for offset in range(7):
            fecha = hoy + datetime.timedelta(days=offset)
            dia_sem = fecha.weekday()
            es_finde = dia_sem in [5, 6]

            for cancha in canchas_creadas:
                for h_ini, h_fin in horas:
                    es_punta = es_finde or (h_ini.hour >= 18)
                    precio = (cancha.precio_base + 4000) if es_punta else (cancha.precio_base - 8000)

                    _, created = BloqueHorario.objects.get_or_create(
                        cancha=cancha,
                        fecha=fecha,
                        hora_inicio=h_ini,
                        defaults={
                            "hora_fin": h_fin,
                            "precio": precio,
                            "es_punta": es_punta,
                            "estado": BloqueHorario.Estado.DISPONIBLE,
                        },
                    )
                    if created:
                        bloques_count += 1

        # 8. Crear una reserva ACEPTADA histórica de muestra
        manana = hoy + datetime.timedelta(days=1)
        bloque_aceptado = BloqueHorario.objects.filter(
            cancha=canchas_creadas[0],
            fecha=manana,
            hora_inicio=datetime.time(20, 0),
        ).first()
        if bloque_aceptado and not bloque_aceptado.reservas.exists():
            bloque_aceptado.estado = BloqueHorario.Estado.RESERVADO
            bloque_aceptado.save()
            Reserva.objects.create(
                bloque=bloque_aceptado,
                usuario=cliente_ivan,
                nombre_cliente="Iván Alejandro",
                rut_cliente="20.987.654-K",
                telefono_cliente="+56 9 9876 5432",
                email_cliente="ivan.futbolito7@yopmail.com",
                estado_reserva=Reserva.EstadoReserva.ACEPTADA,
                estado_pago=Reserva.EstadoPago.PAGADO,
                gestionado_por=admin_mario,
                fecha_gestion=timezone.now(),
                motivo_decision="Reserva verificada y aprobada por administración.",
                monto_total=bloque_aceptado.precio,
                notas="Partido semanal liga nocturna",
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed completado: {len(canchas_creadas)} canchas, 2 admins (admin_mario, admin_eliezer), "
                f"2 clientes validados (cliente_paulo, cliente_ivan) y {bloques_count} bloques nuevos."
            )
        )
