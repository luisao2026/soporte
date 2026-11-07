from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from .models import Usuario


class FormBootstrap:
    """Agrega las clases de Bootstrap a todos los campos del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            w = campo.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault("rows", 3)

    def full_clean(self):
        super().full_clean()
        for nombre in self.errors:
            if nombre in self.fields:
                w = self.fields[nombre].widget
                w.attrs["class"] = (w.attrs.get("class", "") + " is-invalid").strip()


class LoginForm(FormBootstrap, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuario o cédula"
        self.fields["username"].widget.attrs.update({"autofocus": True, "placeholder": "Usuario o cédula"})
        self.fields["password"].widget.attrs.update({"placeholder": "Contraseña"})


class UsuarioForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["cedula", "last_name", "first_name", "email", "celular", "direccion", "cargo", "genero", "rol", "is_active"]
        labels = {"last_name": "Apellidos", "first_name": "Nombres", "email": "Correo", "is_active": "Usuario activo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for c in ("cedula", "last_name", "first_name", "email", "genero", "rol"):
            self.fields[c].required = True
        self.fields["cargo"].widget.attrs["placeholder"] = "Ej.: Docente de Desarrollo de Software"
        self.fields["celular"].widget.attrs["placeholder"] = "09XXXXXXXX"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo.")
        return email

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip().upper()

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip().upper()

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if not usuario.pk:
            # Usuario y contraseña inicial = cédula
            usuario.username = usuario.cedula
            usuario.set_password(usuario.cedula)
        if commit:
            usuario.save()
        return usuario


class PerfilForm(FormBootstrap, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["email", "celular", "direccion"]
        labels = {"email": "Correo"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo.")
        return email


class CambiarClaveForm(FormBootstrap, PasswordChangeForm):
    pass
