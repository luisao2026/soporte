from django.contrib import admin

from .models import Diagnostico, Historial, Mantenimiento, Observacion, Ticket


class DiagnosticoInline(admin.StackedInline):
    model = Diagnostico
    extra = 0


class MantenimientoInline(admin.TabularInline):
    model = Mantenimiento
    extra = 0


class HistorialInline(admin.TabularInline):
    model = Historial
    extra = 0
    readonly_fields = ("fecha", "usuario", "accion")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "solicitante", "equipo", "tipo_soporte", "prioridad", "estado", "practicante")
    list_filter = ("estado", "tipo_soporte", "prioridad")
    search_fields = ("numero", "equipo__codigo", "problema")
    inlines = [DiagnosticoInline, MantenimientoInline, HistorialInline]


admin.site.register(Observacion)
