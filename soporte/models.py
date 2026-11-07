from django.conf import settings
from django.db import models
from django.utils import timezone

from aplicaciones.models import Aplicacion
from equipos.models import Equipo

USUARIO = settings.AUTH_USER_MODEL


class TipoSoporte(models.TextChoices):
    DIAGNOSTICO = "DIAGNOSTICO", "Diagnóstico"
    PREVENTIVO = "PREVENTIVO", "Mantenimiento preventivo"
    CORRECTIVO = "CORRECTIVO", "Mantenimiento correctivo"
    APLICACION = "APLICACION", "Soporte de aplicación"


# Tipos de soporte que aplican a un equipo informático
TIPOS_EQUIPO = [c for c in TipoSoporte.choices if c[0] != TipoSoporte.APLICACION]


class CategoriaApp(models.TextChoices):
    """Qué necesita el usuario de la aplicación."""
    ACCESO = "ACCESO", "Acceso o contraseña"
    CUENTA = "CUENTA", "Creación o activación de usuario"
    CURSOS = "CURSOS", "Cursos, matrículas o permisos"
    CONTENIDO = "CONTENIDO", "Publicación o actualización de contenido"
    ERROR = "ERROR", "Error o falla del sistema"
    CONFIGURACION = "CONFIG", "Configuración o nueva funcionalidad"
    ASESORIA = "ASESORIA", "Asesoría o capacitación"
    OTRO = "OTRO", "Otro"


class Ticket(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ASIGNADO = "ASIGNADO", "Asignado"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        ATENDIDO = "ATENDIDO", "Atendido"
        CERRADO = "CERRADO", "Cerrado"

    class Prioridad(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"
        URGENTE = "URGENTE", "Urgente"

    class Ambito(models.TextChoices):
        EQUIPO = "EQUIPO", "Equipo informático"
        APLICACION = "APLICACION", "Aplicación o plataforma"

    class Resultado(models.TextChoices):
        # Equipos
        REPARADO = "REPARADO", "Equipo reparado"
        NO_REPARADO = "NO_REPARADO", "Equipo no reparado"
        DEVOLUCION = "DEVOLUCION", "Devolución"
        # Aplicaciones
        RESUELTO = "RESUELTO", "Solicitud resuelta"
        NO_RESUELTO = "NO_RESUELTO", "Solicitud no resuelta"
        ESCALADO = "ESCALADO", "Escalado al proveedor / administrador"

    RESULTADOS_EQUIPO = ["REPARADO", "NO_REPARADO", "DEVOLUCION"]
    RESULTADOS_APLICACION = ["RESUELTO", "NO_RESUELTO", "ESCALADO"]

    COLOR_ESTADO = {
        "PENDIENTE": "secondary",
        "ASIGNADO": "info",
        "EN_PROCESO": "warning",
        "ATENDIDO": "primary",
        "CERRADO": "success",
    }
    COLOR_PRIORIDAD = {"BAJA": "secondary", "MEDIA": "info", "ALTA": "warning", "URGENTE": "danger"}
    # Estado en el que queda el equipo según el resultado del soporte
    ESTADO_EQUIPO_POR_RESULTADO = {
        "REPARADO": Equipo.Estado.REPARADO,
        "NO_REPARADO": Equipo.Estado.NO_REPARADO,
        "DEVOLUCION": Equipo.Estado.DEVUELTO,
    }

    numero = models.CharField("Número de ticket", max_length=20, unique=True, null=True, blank=True)
    fecha = models.DateTimeField("Fecha", default=timezone.now)
    solicitante = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="tickets_solicitados", verbose_name="Usuario solicitante")
    ambito = models.CharField("Soporte para", max_length=10, choices=Ambito.choices, default=Ambito.EQUIPO)
    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, null=True, blank=True, related_name="tickets", verbose_name="Equipo")
    aplicacion = models.ForeignKey(Aplicacion, on_delete=models.PROTECT, null=True, blank=True, related_name="tickets",
                                   verbose_name="Aplicación")
    categoria_app = models.CharField("Tipo de solicitud", max_length=10, choices=CategoriaApp.choices, blank=True)
    referencia = models.CharField("Usuario, curso o página afectada", max_length=200, blank=True,
                                  help_text="Ej.: usuario de la plataforma, nombre del curso, enlace de la página.")
    # Copia de los datos del equipo al momento de crear el ticket (historial fiel aunque el equipo cambie)
    marca = models.CharField("Marca", max_length=60, blank=True)
    modelo = models.CharField("Modelo", max_length=80, blank=True)
    numero_serie = models.CharField("Número de serie", max_length=60, blank=True)
    problema = models.TextField("Problema reportado")
    tipo_soporte = models.CharField("Tipo de soporte", max_length=15, choices=TipoSoporte.choices, default=TipoSoporte.DIAGNOSTICO)
    prioridad = models.CharField("Prioridad", max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA)
    estado = models.CharField("Estado", max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)

    practicante = models.ForeignKey(
        USUARIO, on_delete=models.PROTECT, null=True, blank=True, related_name="tickets_asignados", verbose_name="Técnico/practicante"
    )
    asignado_por = models.ForeignKey(USUARIO, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fecha_asignacion = models.DateTimeField("Fecha de asignación", null=True, blank=True)

    resultado = models.CharField("Resultado", max_length=12, choices=Resultado.choices, blank=True)
    detalle_resultado = models.TextField("Detalle del resultado", blank=True)
    fecha_atencion = models.DateTimeField("Fecha de atención", null=True, blank=True)

    fecha_cierre = models.DateTimeField("Fecha de cierre", null=True, blank=True)
    cerrado_por = models.ForeignKey(USUARIO, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    creado_por = models.ForeignKey(USUARIO, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return self.numero or f"Ticket {self.pk}"

    def save(self, *args, **kwargs):
        if not self.marca and self.equipo_id:
            self.marca = self.equipo.marca.nombre
            self.modelo = self.equipo.modelo.nombre
            self.numero_serie = self.equipo.numero_serie
        super().save(*args, **kwargs)
        if not self.numero:
            self.numero = f"TK-{self.fecha.year}-{self.pk:05d}"
            super().save(update_fields=["numero"])

    # ---- Equipo o aplicación ----
    @property
    def es_aplicacion(self):
        return self.ambito == self.Ambito.APLICACION

    @property
    def atendido(self):
        """Nombre de lo que se atiende: el equipo o la aplicación."""
        if self.es_aplicacion:
            return self.aplicacion.nombre if self.aplicacion_id else "—"
        return f"{self.equipo.codigo} - {self.equipo.nombre}" if self.equipo_id else "—"

    @property
    def atendido_detalle(self):
        """Marca y modelo del equipo, o el tipo de solicitud de la aplicación."""
        if self.es_aplicacion:
            return self.get_categoria_app_display()
        return f"{self.marca} {self.modelo}".strip()

    @property
    def resultados_validos(self):
        return self.RESULTADOS_APLICACION if self.es_aplicacion else self.RESULTADOS_EQUIPO

    @property
    def color_estado(self):
        return self.COLOR_ESTADO.get(self.estado, "secondary")

    @property
    def color_prioridad(self):
        return self.COLOR_PRIORIDAD.get(self.prioridad, "secondary")

    @property
    def en_atencion(self):
        """El practicante puede trabajar en el ticket (diagnóstico, mantenimiento, resultado)."""
        return self.estado in (self.Estado.ASIGNADO, self.Estado.EN_PROCESO)

    @property
    def esta_abierto(self):
        return self.estado != self.Estado.CERRADO

    def diagnostico_o_none(self):
        try:
            return self.diagnostico
        except Diagnostico.DoesNotExist:
            return None


class Diagnostico(models.Model):
    class Requiere(models.TextChoices):
        PREVENTIVO = "PREVENTIVO", "Mantenimiento preventivo"
        CORRECTIVO = "CORRECTIVO", "Mantenimiento correctivo"
        NINGUNO = "NINGUNO", "No requiere mantenimiento"
        APLICACION = "APLICACION", "Intervención en la aplicación"

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="diagnostico")
    descripcion = models.TextField("Diagnóstico", help_text="Lo que se encontró al revisar el equipo.")
    causa = models.TextField("Causa probable", blank=True)
    tipo_mantenimiento = models.CharField("Tipo de mantenimiento requerido", max_length=12, choices=Requiere.choices)
    recomendacion = models.TextField("Recomendaciones", blank=True)
    realizado_por = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="diagnosticos", verbose_name="Técnico/practicante")
    fecha = models.DateTimeField("Fecha", default=timezone.now)

    class Meta:
        verbose_name = "diagnóstico"
        verbose_name_plural = "diagnósticos"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Diagnóstico {self.ticket}"


class Mantenimiento(models.Model):
    class Tipo(models.TextChoices):
        PREVENTIVO = "PREVENTIVO", "Preventivo"
        CORRECTIVO = "CORRECTIVO", "Correctivo"
        APLICACION = "APLICACION", "Acción en la aplicación"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="mantenimientos")
    tipo = models.CharField("Tipo de mantenimiento", max_length=12, choices=Tipo.choices)
    actividades = models.TextField("Actividades realizadas")
    repuestos = models.TextField("Repuestos o materiales utilizados", blank=True)
    realizado_por = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="mantenimientos", verbose_name="Técnico/practicante")
    fecha = models.DateTimeField("Fecha", default=timezone.now)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Mantenimiento {self.get_tipo_display().lower()} {self.ticket}"


class Observacion(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="observaciones")
    autor = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    texto = models.TextField("Observación")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "observación"
        verbose_name_plural = "observaciones"
        ordering = ["fecha"]


class Historial(models.Model):
    """Bitácora de todo lo que pasa con un ticket."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="historial")
    usuario = models.ForeignKey(USUARIO, on_delete=models.SET_NULL, null=True, related_name="+")
    accion = models.CharField(max_length=255)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name_plural = "historial"
        ordering = ["fecha", "pk"]
