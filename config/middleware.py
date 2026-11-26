"""
Middleware de cabeceras de seguridad HTTP y control de caché (OWASP Top 10 / ISO 27034).
"""

from django.conf import settings


SENSITIVE_PATH_PREFIXES = (
    "/login/",
    "/registro/",
    "/logout/",
    "/panel-admin/",
    "/mis-reservas/",
    "/comprobante/",
    "/validar-cuenta/",
    "/admin/",
    "/api/reservar/",
    "/api/test-concurrencia/",
)


class SecurityHeadersMiddleware:
    """
    Aplica cabeceras defensivas en todas las respuestas HTTP:
    - Content-Security-Policy (anti-XSS / clickjacking / data exfiltration)
    - Permissions-Policy (deshabilita APIs sensibles del navegador)
    - Referrer-Policy, X-Content-Type-Options, X-Frame-Options, Cross-Origin-Opener-Policy
    - Cache-Control: no-store en sesiones autenticadas y rutas sensibles
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' data: https://lh3.googleusercontent.com",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
        if not settings.DEBUG:
            csp_directives.append("upgrade-insecure-requests")

        response.setdefault("Content-Security-Policy", "; ".join(csp_directives))
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        if "X-Powered-By" in response:
            del response["X-Powered-By"]

        es_autenticado = hasattr(request, "user") and request.user.is_authenticated
        es_ruta_sensible = request.path.startswith(SENSITIVE_PATH_PREFIXES)
        es_estatico = request.path.startswith(("/static/", "/media/"))
        if es_autenticado or es_ruta_sensible or request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        elif not es_estatico:
            response.setdefault("Cache-Control", "no-cache, must-revalidate")

        return response
