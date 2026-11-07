from django.urls import path

from . import views

urlpatterns = [
    path("", views.ticket_lista, name="ticket_lista"),
    path("nuevo/", views.ticket_crear, name="ticket_crear"),
    path("<int:pk>/", views.ticket_detalle, name="ticket_detalle"),
    path("<int:pk>/editar/", views.ticket_editar, name="ticket_editar"),
    path("<int:pk>/asignar/", views.ticket_asignar, name="ticket_asignar"),
    path("<int:pk>/diagnostico/", views.ticket_diagnostico, name="ticket_diagnostico"),
    path("<int:pk>/mantenimiento/", views.ticket_mantenimiento, name="ticket_mantenimiento"),
    path("<int:pk>/resultado/", views.ticket_resultado, name="ticket_resultado"),
    path("<int:pk>/observacion/", views.ticket_observacion, name="ticket_observacion"),
    path("<int:pk>/cerrar/", views.ticket_cerrar, name="ticket_cerrar"),
    path("<int:pk>/estado/", views.ticket_cambiar_estado, name="ticket_cambiar_estado"),
    path("<int:pk>/pdf/", views.ticket_pdf, name="ticket_pdf"),
]
