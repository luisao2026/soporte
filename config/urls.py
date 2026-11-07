from django.contrib import admin
from django.urls import include, path

from soporte.views import inicio

admin.site.site_header = "Soporte de Equipos Informáticos - ISTAM"
admin.site.site_title = "Soporte ISTAM"

urlpatterns = [
    path("", inicio, name="inicio"),
    path("", include("cuentas.urls")),
    path("equipos/", include("equipos.urls")),
    path("aplicaciones/", include("aplicaciones.urls")),
    path("tickets/", include("soporte.urls")),
    path("reportes/", include("reportes.urls")),
    path("admin/", admin.site.urls),
]

handler403 = "cuentas.errores.prohibido"
handler404 = "cuentas.errores.no_encontrado"
