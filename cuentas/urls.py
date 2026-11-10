from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("ingresar/", views.Login.as_view(), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/clave/", views.cambiar_clave, name="cambiar_clave"),
    path("usuarios/", views.usuario_lista, name="usuario_lista"),
    path("usuarios/nuevo/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/carga-masiva/", views.usuario_importar, name="usuario_importar"),
    path("usuarios/carga-masiva/plantilla/", views.usuario_plantilla, name="usuario_plantilla"),
    path("usuarios/carga-masiva/errores/", views.usuario_importar_errores, name="usuario_importar_errores"),
    path("usuarios/<int:pk>/", views.usuario_detalle, name="usuario_detalle"),
    path("usuarios/<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/estado/", views.usuario_cambiar_estado, name="usuario_cambiar_estado"),
    path("usuarios/<int:pk>/restablecer-clave/", views.usuario_restablecer_clave, name="usuario_restablecer_clave"),
]
