from django.urls import path

from . import views

urlpatterns = [
    path("", views.equipo_lista, name="equipo_lista"),
    path("nuevo/", views.equipo_crear, name="equipo_crear"),
    path("<int:pk>/", views.equipo_detalle, name="equipo_detalle"),
    path("<int:pk>/editar/", views.equipo_editar, name="equipo_editar"),
    path("catalogos/", views.catalogos, name="catalogos"),
    path("catalogos/<str:tipo>/<int:pk>/", views.catalogo_editar, name="catalogo_editar"),
    path("catalogos/<str:tipo>/<int:pk>/estado/", views.catalogo_estado, name="catalogo_estado"),
]
