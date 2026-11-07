from django.conf import settings


def institucion(request):
    return {
        "INSTITUCION_NOMBRE": settings.INSTITUCION_NOMBRE,
        "INSTITUCION_SIGLAS": settings.INSTITUCION_SIGLAS,
        "DEPARTAMENTO_TIC": settings.DEPARTAMENTO_TIC,
    }
