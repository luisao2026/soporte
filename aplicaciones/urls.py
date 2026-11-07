from django.urls import path

from . import views

urlpatterns = [
    path("", views.aplicacion_lista, name="aplicacion_lista"),
    path("nueva/", views.aplicacion_crear, name="aplicacion_crear"),
    path("<int:pk>/", views.aplicacion_detalle, name="aplicacion_detalle"),
    path("<int:pk>/editar/", views.aplicacion_editar, name="aplicacion_editar"),
    path("<int:pk>/estado/", views.aplicacion_estado, name="aplicacion_estado"),
]
