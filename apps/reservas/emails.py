from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def enviar_correo_documento_reserva(reserva, request=None) -> bool:
    """
    Envía por correo electrónico el Documento Oficial de Reserva al cliente,
    indicando su etapa actual (EN ESPERA, ACEPTADA o DENEGADA), los datos del
    cliente y los datos completos de la cancha solicitada.
    """
    etapa_map = {
        "EN_ESPERA": ("🟡 EN ESPERA DE APROBACIÓN", "#d97706", "Tu solicitud ha sido recibida y está siendo revisada por un administrador."),
        "ACEPTADA": ("🟢 RESERVA ACEPTADA Y CONFIRMADA", "#16a34a", "¡Tu reserva fue aprobada por la administración! Tu cancha está 100% asegurada."),
        "DENEGADA": ("🔴 RESERVA DENEGADA", "#dc2626", "Tu solicitud de reserva fue denegada por la administración. El horario ha sido liberado y ya puedes solicitar otro turno."),
    }
    titulo_etapa, color_hex, descripcion_etapa = etapa_map.get(
        reserva.estado_reserva,
        ("🟡 EN ESPERA DE APROBACIÓN", "#d97706", "Estado en revisión.")
    )

    cancha = reserva.bloque.cancha
    complejo = cancha.complejo
    fecha_str = reserva.bloque.fecha.strftime("%d/%m/%Y")
    horario_str = f"{reserva.bloque.hora_inicio.strftime('%H:%M')} - {reserva.bloque.hora_fin.strftime('%H:%M')} hrs"
    admin_nombre = (
        reserva.gestionado_por.get_full_name() or reserva.gestionado_por.username
        if reserva.gestionado_por else "Pendiente de revisión"
    )

    base_url = ""
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
    else:
        base_url = getattr(settings, "SITE_URL", "http://localhost:8000")

    url_comprobante = f"{base_url}/comprobante/{reserva.codigo}/"

    asunto = f"[Futbolito 7] Documento de Reserva #{str(reserva.codigo)[:8].upper()} — {reserva.get_estado_reserva_display()}"

    texto_plano = (
        f"DOCUMENTO OFICIAL DE RESERVA — FUTBOLITO 7\n"
        f"=================================================\n"
        f"ESTADO ACTUAL: {titulo_etapa}\n"
        f"{descripcion_etapa}\n\n"
        f"1. DATOS DEL CLIENTE:\n"
        f"- Código de Reserva: {reserva.codigo}\n"
        f"- Nombre Titular: {reserva.nombre_cliente}\n"
        f"- RUT: {reserva.rut_cliente or 'No especificado'}\n"
        f"- Teléfono: {reserva.telefono_cliente}\n"
        f"- Correo: {reserva.email_cliente}\n\n"
        f"2. DATOS DE LA CANCHA SOLICITADA:\n"
        f"- Complejo: {complejo.nombre} ({complejo.direccion}, {complejo.comuna})\n"
        f"- Cancha: {cancha.nombre}\n"
        f"- Medidas: {cancha.medidas}\n"
        f"- Superficie: {cancha.superficie.nombre}\n"
        f"- Tipo: {'Techada' if cancha.techada else 'Al Aire Libre'}\n"
        f"- Fecha: {fecha_str}\n"
        f"- Horario: {horario_str}\n"
        f"- Monto Total: ${reserva.monto_total:,.0f} CLP\n\n"
        f"3. RESOLUCIÓN ADMINISTRATIVA:\n"
        f"- Revisado por: {admin_nombre}\n"
        f"- Observación: {reserva.motivo_decision or 'Sin observaciones adicionales'}\n\n"
        f"Ver Documento Oficial de Reserva en línea:\n{url_comprobante}\n"
    )

    html_content = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 640px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; background-color: #ffffff; color: #1e293b;">
        <div style="background-color: #0f172a; padding: 24px; text-align: center; color: #ffffff;">
            <h1 style="margin: 0; font-size: 22px; letter-spacing: 1px;">⚽ FUTBOLITO 7 — DOCUMENTO DE RESERVA</h1>
            <p style="margin: 6px 0 0; font-size: 12px; color: #94a3b8;">Código Oficial: {reserva.codigo}</p>
        </div>

        <div style="padding: 24px;">
            <div style="background-color: {color_hex}15; border-left: 5px solid {color_hex}; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
                <div style="font-size: 16px; font-weight: bold; color: {color_hex};">{titulo_etapa}</div>
                <p style="margin: 6px 0 0; font-size: 13px; color: #334155;">{descripcion_etapa}</p>
            </div>

            <h3 style="font-size: 14px; text-transform: uppercase; color: #475569; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">1. Datos del Cliente</h3>
            <table style="width: 100%; font-size: 14px; margin-bottom: 20px;">
                <tr><td style="padding: 4px 0; color: #64748b;">Nombre Titular:</td><td style="padding: 4px 0; font-weight: bold;">{reserva.nombre_cliente}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">RUT:</td><td style="padding: 4px 0; font-weight: bold;">{reserva.rut_cliente or 'Registrado en perfil'}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Teléfono:</td><td style="padding: 4px 0;">{reserva.telefono_cliente}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Correo Electrónico:</td><td style="padding: 4px 0;">{reserva.email_cliente}</td></tr>
            </table>

            <h3 style="font-size: 14px; text-transform: uppercase; color: #475569; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">2. Datos de la Cancha Solicitada</h3>
            <table style="width: 100%; font-size: 14px; margin-bottom: 20px;">
                <tr><td style="padding: 4px 0; color: #64748b;">Complejo:</td><td style="padding: 4px 0; font-weight: bold;">{complejo.nombre}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Cancha:</td><td style="padding: 4px 0; font-weight: bold; color: #0f172a;">{cancha.nombre}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Medidas Oficiales:</td><td style="padding: 4px 0;">{cancha.medidas}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Superficie:</td><td style="padding: 4px 0;">{cancha.superficie.nombre} ({'Techada' if cancha.techada else 'Al Aire Libre'})</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Fecha del Partido:</td><td style="padding: 4px 0; font-weight: bold;">{fecha_str}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Bloque Horario:</td><td style="padding: 4px 0; font-weight: bold; color: #16a34a;">{horario_str}</td></tr>
                <tr><td style="padding: 4px 0; color: #64748b;">Valor Total:</td><td style="padding: 4px 0; font-size: 16px; font-weight: bold;">${reserva.monto_total:,.0f} CLP</td></tr>
            </table>

            <h3 style="font-size: 14px; text-transform: uppercase; color: #475569; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">3. Estado de Revisión Administrativa</h3>
            <p style="font-size: 13px; color: #475569; margin: 6px 0;">
                <strong>Administrador revisor:</strong> {admin_nombre}<br>
                <strong>Observación:</strong> {reserva.motivo_decision or 'En espera de confirmación por recepción.'}
            </p>

            <div style="text-align: center; margin-top: 28px;">
                <a href="{url_comprobante}" style="background-color: #16a34a; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 14px; display: inline-block;">
                    Ver / Imprimir Documento de Reserva
                </a>
            </div>
        </div>
    </div>
    """

    try:
        msg = EmailMultiAlternatives(
            subject=asunto,
            body=texto_plano,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "notificaciones@futbolito7.cl"),
            to=[reserva.email_cliente],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
        return True
    except Exception:
        return False


def enviar_correo_validacion_cuenta(perfil, request=None) -> bool:
    """
    Envía correo de activación/validación al registrar una cuenta de cliente.
    Compatible con servicios de correo temporal/ficticio (Yopmail, Mailtrap, Temp-Mail).
    """
    base_url = f"{request.scheme}://{request.get_host()}" if request else getattr(settings, "SITE_URL", "http://localhost:8000")
    url_activar = f"{base_url}/validar-cuenta/{perfil.token_validacion}/"
    usuario = perfil.usuario
    nombre = usuario.get_full_name() or usuario.username

    asunto = "[Futbolito 7] Valida tu cuenta de Jugador / Cliente"
    cuerpo = (
        f"Hola {nombre},\n\n"
        f"Tu cuenta de Cliente en Futbolito 7 ha sido registrada exitosamente.\n"
        f"Para confirmar y validar tu correo electrónico, ingresa al siguiente enlace:\n"
        f"{url_activar}\n\n"
        f"RUT registrado: {perfil.rut}\n"
        f"Rol asignado: Cliente / Jugador\n"
    )
    html_validacion = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e7e5e4; border-radius: 16px; overflow: hidden; background-color: #fbf9f4; color: #1b1c19;">
        <div style="background-color: #1c1917; padding: 24px; text-align: center; color: #ffffff;">
            <h1 style="margin: 0; font-size: 22px; letter-spacing: 1px;">⚽ FUTBOLITO 7 — ACTIVACIÓN DE CUENTA</h1>
            <p style="margin: 6px 0 0; font-size: 12px; color: #fe932c;">Portal Oficial de Jugadores</p>
        </div>
        <div style="padding: 28px;">
            <h2 style="margin-top: 0; color: #a33900;">¡Hola, {nombre}!</h2>
            <p style="font-size: 14px; line-height: 1.6; color: #44403c;">
                Tu perfil de <strong>Cliente / Jugador</strong> (RUT: <code>{perfil.rut}</code>) ha sido creado en <strong>Futbolito 7 Club Deportivo</strong>.
                Para habilitar la reserva de canchas en tiempo real, confirma tu correo haciendo clic en el botón:
            </p>
            <div style="text-align: center; margin: 28px 0;">
                <a href="{url_activar}" style="background-color: #a33900; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 10px; font-weight: bold; font-size: 14px; display: inline-block;">
                    ✓ Validar mi Cuenta en 1 Clic
                </a>
            </div>
            <p style="font-size: 12px; color: #78716c;">
                O copia y pega este enlace en tu navegador:<br>
                <a href="{url_activar}" style="color: #a33900;">{url_activar}</a>
            </p>
        </div>
    </div>
    """
    try:
        msg = EmailMultiAlternatives(
            subject=asunto,
            body=cuerpo,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "notificaciones@futbolito7.cl"),
            to=[usuario.email],
        )
        msg.attach_alternative(html_validacion, "text/html")
        msg.send(fail_silently=True)
        return True
    except Exception:
        return False
