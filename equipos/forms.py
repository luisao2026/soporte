from django import forms
from django.contrib.auth import get_user_model

from cuentas.forms import FormBootstrap

from .models import Categoria, Equipo, Marca, Modelo


class EquipoForm(FormBootstrap, forms.ModelForm):
    otro_modelo = forms.CharField(
        label="¿El modelo no está en la lista? Escríbalo aquí", max_length=80, required=False,
        help_text="Se registrará automáticamente en la marca seleccionada.",
    )

    class Meta:
        model = Equipo
        fields = ["codigo", "nombre", "categoria", "marca", "modelo", "numero_serie", "especificaciones", "responsable", "estado"]
        widgets = {"especificaciones": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        inst = self.instance
        self.fields["categoria"].queryset = Categoria.objects.filter(activo=True) | Categoria.objects.filter(pk=inst.categoria_id or 0)
        self.fields["marca"].queryset = Marca.objects.filter(activo=True) | Marca.objects.filter(pk=inst.marca_id or 0)
        self.fields["modelo"].queryset = (
            Modelo.objects.filter(activo=True) | Modelo.objects.filter(pk=inst.modelo_id or 0)
        ).select_related("marca")
        self.fields["modelo"].required = False
        self.fields["modelo"].label_from_instance = lambda m: m.nombre
        self.fields["nombre"].widget.attrs["placeholder"] = "Ej.: Laptop del aula 3 / Computador de secretaría"
        self.fields["codigo"].widget.attrs["placeholder"] = "Se genera automáticamente si lo deja vacío"
        self.fields["codigo"].help_text = "Ej.: código del inventario institucional."

        if usuario and usuario.es_admin:
            Usuario = get_user_model()
            self.fields["responsable"].queryset = Usuario.objects.filter(is_active=True) | Usuario.objects.filter(pk=inst.responsable_id or 0)
        else:
            # Docentes y estudiantes registran equipos a su nombre y no cambian el estado
            for c in ("responsable", "estado", "codigo"):
                del self.fields[c]

    def clean_numero_serie(self):
        serie = self.cleaned_data["numero_serie"].strip().upper()
        if Equipo.objects.filter(numero_serie__iexact=serie).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un equipo con este número de serie.")
        return serie

    def clean_codigo(self):
        codigo = (self.cleaned_data.get("codigo") or "").strip().upper()
        if not codigo:
            return self.instance.codigo or None
        if Equipo.objects.filter(codigo__iexact=codigo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un equipo con este código.")
        return codigo

    def clean(self):
        datos = super().clean()
        marca, modelo, otro = datos.get("marca"), datos.get("modelo"), (datos.get("otro_modelo") or "").strip()
        if marca and otro:
            datos["modelo"], _ = Modelo.objects.get_or_create(marca=marca, nombre__iexact=otro, defaults={"nombre": otro})
            self.instance.modelo = datos["modelo"]
        elif not modelo:
            self.add_error("modelo", "Seleccione el modelo o escríbalo en el campo de abajo.")
        elif marca and modelo.marca_id != marca.pk:
            self.add_error("modelo", "El modelo no corresponde a la marca seleccionada.")
        return datos

    def save(self, commit=True):
        equipo = super().save(commit=False)
        equipo.modelo = self.cleaned_data["modelo"]
        if commit:
            equipo.save()
        return equipo


class CategoriaForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "activo"]
        widgets = {"nombre": forms.TextInput(attrs={"placeholder": "Nueva categoría"})}


class MarcaForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Marca
        fields = ["nombre", "activo"]
        widgets = {"nombre": forms.TextInput(attrs={"placeholder": "Nueva marca"})}


class ModeloForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Modelo
        fields = ["marca", "nombre", "activo"]
        widgets = {"nombre": forms.TextInput(attrs={"placeholder": "Nuevo modelo"})}

    def clean(self):
        datos = super().clean()
        if datos.get("marca") and datos.get("nombre"):
            existe = Modelo.objects.filter(marca=datos["marca"], nombre__iexact=datos["nombre"].strip()).exclude(pk=self.instance.pk)
            if existe.exists():
                raise forms.ValidationError("Ese modelo ya está registrado para la marca.")
        return datos
