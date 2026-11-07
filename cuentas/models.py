from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validar_cedula, validar_celular


class Usuario(AbstractUser):
    """Usuario del sistema. Nombres = first_name, Apellidos = last_name, Estado = is_active."""

    class Rol(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        TIC = "TIC", "Responsable de TIC"
        PRACTICANTE = "PRACTICANTE", "Practicante"
        DOCENTE = "DOCENTE", "Docente"
        ESTUDIANTE = "ESTUDIANTE", "Estudiante"

    class Genero(models.TextChoices):
        MASCULINO = "M", "Masculino"
        FEMENINO = "F", "Femenino"
        OTRO = "O", "Otro"

    cedula = models.CharField("Cédula", max_length=10, unique=True, null=True, blank=True, validators=[validar_cedula])
    celular = models.CharField("Celular", max_length=10, blank=True, validators=[validar_celular])
    direccion = models.CharField("Dirección", max_length=200, blank=True)
    cargo = models.CharField("Cargo", max_length=100, blank=True)
    genero = models.CharField("Género", max_length=1, choices=Genero.choices, blank=True)
    rol = models.CharField("Rol", max_length=15, choices=Rol.choices, default=Rol.ESTUDIANTE)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.nombre_completo

    def save(self, *args, **kwargs):
        # El superusuario creado con "createsuperuser" queda como Administrador
        if self.is_superuser and not self.pk:
            self.rol = self.Rol.ADMIN
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        nombre = f"{self.last_name} {self.first_name}".strip()
        return nombre or self.username

    # ---- Ayudas de rol ----
    @property
    def es_admin(self):
        return self.is_superuser or self.rol == self.Rol.ADMIN

    @property
    def es_tic(self):
        return self.rol == self.Rol.TIC

    @property
    def es_practicante(self):
        return self.rol == self.Rol.PRACTICANTE

    @property
    def es_solicitante(self):
        """Docentes y estudiantes: registran sus equipos y crean tickets."""
        return not self.is_superuser and self.rol in (self.Rol.DOCENTE, self.Rol.ESTUDIANTE)

    @property
    def es_personal_tic(self):
        """Quienes ven todos los tickets y equipos: Administrador y Responsable de TIC."""
        return self.es_admin or self.es_tic

    @property
    def rol_efectivo(self):
        return self.Rol.ADMIN if self.is_superuser else self.rol

    @property
    def puede_ver_reportes(self):
        from django.conf import settings
        return self.rol_efectivo in settings.ROLES_REPORTES

    @property
    def puede_crear_tickets(self):
        return self.es_admin or self.es_solicitante

    def get_rol_display_efectivo(self):
        return "Administrador" if self.is_superuser and self.rol != self.Rol.ADMIN else self.get_rol_display()
