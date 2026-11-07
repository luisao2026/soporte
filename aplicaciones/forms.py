from django import forms

from cuentas.forms import FormBootstrap
from cuentas.models import Usuario

from .models import Aplicacion


class AplicacionForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Aplicacion
        fields = ["nombre", "plataforma", "tipo", "url", "responsable", "proveedor", "descripcion", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2}),
                   "url": forms.URLInput(attrs={"placeholder": "https://eva.istam.edu.ec"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        actual = self.instance.responsable_id or 0
        self.fields["responsable"].queryset = Usuario.objects.filter(
            is_active=True, rol__in=[Usuario.Rol.ADMIN, Usuario.Rol.TIC, Usuario.Rol.PRACTICANTE]
        ) | Usuario.objects.filter(pk=actual) | Usuario.objects.filter(is_superuser=True)
        self.fields["responsable"].queryset = self.fields["responsable"].queryset.distinct()
        self.fields["responsable"].empty_label = "Sin asignar"

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        if Aplicacion.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una aplicación con este nombre.")
        return nombre
