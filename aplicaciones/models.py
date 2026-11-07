from django.conf import settings
from django.db import models


class Aplicacion(models.Model):
    """Sistema o plataforma institucional a la que el Departamento de TIC da soporte (EVA/Moodle, WordPress, SIGA...)."""

    class Tipo(models.TextChoices):
        EDUCATIVA = "EDUCATIVA", "Plataforma educativa"
        WEB = "WEB", "Sitio web"
        ACADEMICO = "ACADEMICO", "Sistema académico / administrativo"
        CORREO = "CORREO", "Correo y colaboración"
        OTRO = "OTRO", "Otro"

    nombre = models.CharField("Nombre", max_length=80, unique=True, help_text="Ej.: EVA - Entorno Virtual de Aprendizaje")
    plataforma = models.CharField("Plataforma / tecnología", max_length=60, blank=True, help_text="Ej.: Moodle 4.3, WordPress, Google Workspace")
    tipo = models.CharField("Tipo", max_length=12, choices=Tipo.choices, default=Tipo.OTRO)
    url = models.URLField("Dirección (URL)", blank=True)
    descripcion = models.TextField("Descripción", blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="aplicaciones_a_cargo",
        verbose_name="Responsable técnico", help_text="Persona del Departamento de TIC que administra la aplicación.",
    )
    proveedor = models.CharField("Proveedor / soporte externo", max_length=120, blank=True,
                                 help_text="A quién se escala si el problema no se resuelve internamente.")
    activo = models.BooleanField("Activa", default=True)

    class Meta:
        verbose_name = "aplicación"
        verbose_name_plural = "aplicaciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    ICONO_TIPO = {"EDUCATIVA": "bi-mortarboard", "WEB": "bi-globe2", "ACADEMICO": "bi-building-gear",
                  "CORREO": "bi-envelope-at", "OTRO": "bi-app-indicator"}

    @property
    def icono(self):
        return self.ICONO_TIPO.get(self.tipo, "bi-app-indicator")
