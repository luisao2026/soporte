from django.contrib import admin

from .models import Categoria, Equipo, Marca, Modelo

admin.site.register(Categoria)
admin.site.register(Marca)


@admin.register(Modelo)
class ModeloAdmin(admin.ModelAdmin):
    list_display = ("nombre", "marca", "activo")
    list_filter = ("marca",)


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "categoria", "marca", "modelo", "numero_serie", "responsable", "estado")
    list_filter = ("estado", "categoria", "marca")
    search_fields = ("codigo", "nombre", "numero_serie")
