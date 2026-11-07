from django.contrib import admin

from .models import Aplicacion


@admin.register(Aplicacion)
class AplicacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "plataforma", "tipo", "url", "responsable", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("nombre", "plataforma")
