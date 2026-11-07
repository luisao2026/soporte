from django.conf import settings
from django.db import models
from django.utils import timezone


class Categoria(models.Model):
    """Tipo de equipo: Tablet, Laptop, Proyector, etc."""

    nombre = models.CharField("Nombre", max_length=60, unique=True)
    activo = models.BooleanField("Activa", default=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Marca(models.Model):
    nombre = models.CharField("Nombre", max_length=60, unique=True)
    activo = models.BooleanField("Activa", default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Modelo(models.Model):
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, related_name="modelos", verbose_name="Marca")
    nombre = models.CharField("Modelo", max_length=80)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        ordering = ["marca__nombre", "nombre"]
        constraints = [models.UniqueConstraint(fields=["marca", "nombre"], name="modelo_unico_por_marca")]

    def __str__(self):
        return f"{self.marca} {self.nombre}"


class Equipo(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        MANTENIMIENTO = "MANTENIMIENTO", "En mantenimiento"
        REPARADO = "REPARADO", "Reparado"
        NO_REPARADO = "NO_REPARADO", "No reparado"
        DEVUELTO = "DEVUELTO", "Devuelto"
        BAJA = "BAJA", "Dado de baja"

    COLOR_ESTADO = {
        "ACTIVO": "success",
        "MANTENIMIENTO": "warning",
        "REPARADO": "primary",
        "NO_REPARADO": "danger",
        "DEVUELTO": "secondary",
        "BAJA": "dark",
    }

    codigo = models.CharField("Código del equipo", max_length=20, unique=True, null=True, blank=True)
    nombre = models.CharField("Nombre del equipo", max_length=100)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="equipos", verbose_name="Tipo de equipo")
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, related_name="equipos", verbose_name="Marca")
    modelo = models.ForeignKey(Modelo, on_delete=models.PROTECT, related_name="equipos", verbose_name="Modelo")
    numero_serie = models.CharField("Número de serie", max_length=60, unique=True)
    especificaciones = models.TextField("Especificaciones", blank=True, help_text="Procesador, RAM, disco, sistema operativo, etc.")
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="equipos", verbose_name="Usuario responsable"
    )
    estado = models.CharField("Estado", max_length=15, choices=Estado.choices, default=Estado.ACTIVO)
    fecha_registro = models.DateTimeField("Fecha de registro", default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        self.numero_serie = self.numero_serie.strip().upper()
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = f"EQ-{self.pk:05d}"
            super().save(update_fields=["codigo"])

    @property
    def color_estado(self):
        return self.COLOR_ESTADO.get(self.estado, "secondary")

    @property
    def ticket_abierto(self):
        from soporte.models import Ticket
        return self.tickets.exclude(estado=Ticket.Estado.CERRADO).first()
