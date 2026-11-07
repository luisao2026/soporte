from django import forms

from aplicaciones.models import Aplicacion
from cuentas.forms import FormBootstrap
from cuentas.models import Usuario
from equipos.models import Equipo

from .models import TIPOS_EQUIPO, CategoriaApp, Diagnostico, Mantenimiento, Ticket, TipoSoporte


class EquipoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, e):
        texto = f"{e.codigo} · {e.nombre} · {e.marca} {e.modelo.nombre} · Serie {e.numero_serie}"
        return texto


class TicketForm(FormBootstrap, forms.ModelForm):
    """Ticket de soporte para un equipo informático."""
    equipo = EquipoChoiceField(queryset=Equipo.objects.none(), label="Equipo")
    solicitante = forms.ModelChoiceField(
        queryset=Usuario.objects.none(), required=False, label="Usuario solicitante",
        help_text="Si lo deja vacío se usa el responsable del equipo.",
    )

    class Meta:
        model = Ticket
        fields = ["equipo", "solicitante", "problema", "tipo_soporte", "prioridad"]
        widgets = {"problema": forms.Textarea(attrs={"rows": 4, "placeholder": "Describa la falla: qué pasa, desde cuándo, mensajes de error..."})}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo_soporte"].choices = TIPOS_EQUIPO
        equipos = Equipo.objects.exclude(estado=Equipo.Estado.BAJA).exclude(
            tickets__estado__in=[e for e in Ticket.Estado.values if e != Ticket.Estado.CERRADO]
        ).select_related("marca", "modelo", "responsable")
        if self.instance.pk:  # edición: mantener el equipo actual
            equipos = Equipo.objects.filter(pk=self.instance.equipo_id).select_related("marca", "modelo") | equipos
        if usuario.es_admin:
            self.fields["solicitante"].queryset = Usuario.objects.filter(is_active=True)
        else:
            equipos = equipos.filter(responsable=usuario)
            del self.fields["solicitante"]
        self.fields["equipo"].queryset = equipos.distinct()
        self.fields["equipo"].empty_label = "Seleccione el equipo"


class TicketAplicacionForm(FormBootstrap, forms.ModelForm):
    """Ticket de soporte para una aplicación (EVA/Moodle, WordPress, SIGA...)."""
    solicitante = forms.ModelChoiceField(
        queryset=Usuario.objects.none(), required=False, label="Usuario solicitante",
        help_text="Si lo deja vacío, el ticket queda a su nombre.",
    )

    class Meta:
        model = Ticket
        fields = ["aplicacion", "categoria_app", "solicitante", "referencia", "problema", "prioridad"]
        widgets = {
            "problema": forms.Textarea(attrs={"rows": 4, "placeholder": "Describa lo que necesita o el error que aparece: "
                                                                       "qué estaba haciendo, mensaje que muestra, desde cuándo..."}),
            "referencia": forms.TextInput(attrs={"placeholder": "Ej.: usuario 1712345678, curso Programación I, enlace de la página"}),
        }
        labels = {"problema": "Detalle de la solicitud"}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        actual = self.instance.aplicacion_id or 0
        self.fields["aplicacion"].queryset = Aplicacion.objects.filter(activo=True) | Aplicacion.objects.filter(pk=actual)
        self.fields["aplicacion"].required = True
        self.fields["aplicacion"].empty_label = "Seleccione la aplicación"
        self.fields["categoria_app"].required = True
        self.fields["categoria_app"].choices = [("", "Seleccione el tipo de solicitud")] + list(CategoriaApp.choices)
        if usuario.es_admin and not self.instance.pk:
            self.fields["solicitante"].queryset = Usuario.objects.filter(is_active=True)
        else:
            del self.fields["solicitante"]


class AsignarForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["practicante", "tipo_soporte", "prioridad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["practicante"].required = True
        self.fields["practicante"].queryset = Usuario.objects.filter(is_active=True, rol=Usuario.Rol.PRACTICANTE)
        self.fields["practicante"].empty_label = "Seleccione el practicante"
        if self.instance.es_aplicacion:
            del self.fields["tipo_soporte"]  # siempre "Soporte de aplicación"
        else:
            self.fields["tipo_soporte"].choices = TIPOS_EQUIPO


class DiagnosticoForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Diagnostico
        fields = ["descripcion", "causa", "tipo_mantenimiento", "recomendacion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3}), "causa": forms.Textarea(attrs={"rows": 2}),
                   "recomendacion": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo_mantenimiento"].choices = [
            c for c in Diagnostico.Requiere.choices if c[0] != Diagnostico.Requiere.APLICACION]


class AnalisisAppForm(FormBootstrap, forms.ModelForm):
    """Análisis del problema en una aplicación (equivale al diagnóstico de un equipo)."""
    class Meta:
        model = Diagnostico
        fields = ["descripcion", "causa", "recomendacion"]
        labels = {"descripcion": "Análisis del problema", "causa": "Causa identificada",
                  "recomendacion": "Recomendaciones al usuario"}
        help_texts = {"descripcion": "Qué se revisó y qué se encontró (registros, permisos, configuración...)."}
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3}), "causa": forms.Textarea(attrs={"rows": 2}),
                   "recomendacion": forms.Textarea(attrs={"rows": 2})}

    def save(self, commit=True):
        self.instance.tipo_mantenimiento = Diagnostico.Requiere.APLICACION
        return super().save(commit)


class MantenimientoForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Mantenimiento
        fields = ["tipo", "actividades", "repuestos"]
        widgets = {
            "actividades": forms.Textarea(attrs={"rows": 3, "placeholder": "Limpieza interna, cambio de pasta térmica, reinstalación del sistema..."}),
            "repuestos": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [c for c in Mantenimiento.Tipo.choices if c[0] != Mantenimiento.Tipo.APLICACION]


class AccionAppForm(FormBootstrap, forms.ModelForm):
    """Acciones realizadas en la aplicación (equivale al mantenimiento de un equipo)."""
    class Meta:
        model = Mantenimiento
        fields = ["actividades", "repuestos"]
        labels = {"actividades": "Acciones realizadas", "repuestos": "Herramientas o referencias (opcional)"}
        widgets = {
            "actividades": forms.Textarea(attrs={"rows": 3, "placeholder": "Restablecimiento de contraseña, matriculación en el curso, "
                                                                           "corrección de permisos, actualización del plugin..."}),
            "repuestos": forms.Textarea(attrs={"rows": 2, "placeholder": "Panel de administración, ticket del proveedor, documentación..."}),
        }


class ResultadoForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["resultado", "detalle_resultado"]
        widgets = {"detalle_resultado": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resultado"].required = True
        self.fields["detalle_resultado"].required = True
        validos = self.instance.resultados_validos
        self.fields["resultado"].choices = [("", "Seleccione el resultado")] + [
            c for c in Ticket.Resultado.choices if c[0] in validos]


class ObservacionForm(FormBootstrap, forms.Form):
    texto = forms.CharField(label="Observación", widget=forms.Textarea(attrs={"rows": 2}))


class CerrarForm(FormBootstrap, forms.Form):
    comentario = forms.CharField(label="Comentario de cierre (opcional)", required=False, max_length=200)


class CambiarEstadoForm(FormBootstrap, forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado", choices=Ticket.Estado.choices)
    motivo = forms.CharField(label="Motivo", max_length=200)


class FiltroTicketForm(FormBootstrap, forms.Form):
    q = forms.CharField(required=False, label="Buscar", widget=forms.TextInput(attrs={"placeholder": "N.º, equipo, aplicación, solicitante"}))
    ambito = forms.ChoiceField(required=False, choices=[("", "Equipos y aplicaciones")] + list(Ticket.Ambito.choices))
    estado = forms.ChoiceField(required=False, choices=[("", "Todos los estados")] + list(Ticket.Estado.choices))
    tipo = forms.ChoiceField(required=False, choices=[("", "Todos los tipos")] + list(TipoSoporte.choices))
    prioridad = forms.ChoiceField(required=False, choices=[("", "Todas las prioridades")] + list(Ticket.Prioridad.choices))
    practicante = forms.ModelChoiceField(required=False, queryset=Usuario.objects.filter(rol=Usuario.Rol.PRACTICANTE), empty_label="Todos los practicantes")
