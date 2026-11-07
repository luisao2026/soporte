from django.shortcuts import render


def prohibido(request, exception=None):
    mensaje = str(exception) if exception and str(exception) else "No tiene permiso para acceder a esta sección."
    return render(request, "error.html", {"codigo": 403, "titulo": "Acceso no permitido", "mensaje": mensaje}, status=403)


def no_encontrado(request, exception=None):
    return render(request, "error.html", {"codigo": 404, "titulo": "Página no encontrada",
                                          "mensaje": "El registro no existe o no tiene acceso a él."}, status=404)
