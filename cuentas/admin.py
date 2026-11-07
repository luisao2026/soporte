from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "cedula", "last_name", "first_name", "rol", "is_active")
    list_filter = ("rol", "is_active", "genero")
    search_fields = ("username", "cedula", "first_name", "last_name", "email")
    fieldsets = UserAdmin.fieldsets + (
        ("Datos institucionales", {"fields": ("cedula", "celular", "direccion", "cargo", "genero", "rol")}),
    )
