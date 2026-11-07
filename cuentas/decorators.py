from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def rol_requerido(*roles):
    """Permite el acceso solo a los roles indicados. El superusuario siempre entra como Administrador."""

    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.user.rol_efectivo not in roles:
                raise PermissionDenied("No tiene permiso para acceder a esta sección.")
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


def reportes_requeridos(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.puede_ver_reportes:
            raise PermissionDenied("Los reportes solo están disponibles para el Administrador y el Practicante.")
        return vista(request, *args, **kwargs)

    return envoltura
