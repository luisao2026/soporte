from django.urls import path

from . import views

urlpatterns = [
    path("", views.indice, name="reportes"),
    path("tickets/", views.reporte_tickets, name="reporte_tickets"),
    path("diagnosticos/", views.reporte_diagnosticos, name="reporte_diagnosticos"),
    path("mantenimientos/", views.reporte_mantenimientos, name="reporte_mantenimientos"),
    path("tipos-de-soporte/", views.reporte_tipos, name="reporte_tipos"),
    path("aplicaciones/", views.reporte_aplicaciones, name="reporte_aplicaciones"),
]
