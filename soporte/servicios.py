"""
Reglas del proceso de soporte técnico:
Registro del ticket → Asignación → Diagnóstico → Mantenimiento (preventivo/correctivo)
→ Resultado (reparado / no reparado / devolución) → Cierre.

Los tickets de aplicaciones (EVA/Moodle, WordPress, SIGA...) siguen el mismo flujo:
Registro → Asignación → Análisis → Acciones realizadas → Resultado (resuelto / no resuelto / escalado) → Cierre.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from cuentas.models import Usuario
from equipos.models import Equipo

from .models import Diagnostico, Historial, Mantenimiento, Ticket, TipoSoporte

log = logging.getLogger(__name__)


class FlujoError(Exception):
    """Acción no permitida en el estado actual del ticket."""


def registrar(ticket, usuario, accion):
    Historial.objects.create(ticket=ticket, usuario=usuario, accion=accion)


def notificar(asunto, mensaje, destinatarios, enlace=""):
    correos = sorted({d.email for d in destinatarios if d and d.email})
    if not correos:
        return
    cuerpo = mensaje + (f"\n\nVer el ticket: {enlace}" if enlace else "")
    cuerpo += f"\n\n--\n{settings.DEPARTAMENTO_TIC}\n{settings.INSTITUCION_NOMBRE}"
    try:
        send_mail(f"[Soporte {settings.INSTITUCION_SIGLAS}] {asunto}", cuerpo, settings.DEFAULT_FROM_EMAIL, correos)
    except Exception:  # un fallo del correo no debe detener el sistema
        log.exception("No se pudo enviar el correo: %s", asunto)


def _administradores():
    return Usuario.objects.filter(is_active=True, rol__in=[Usuario.Rol.ADMIN, Usuario.Rol.TIC])


@transaction.atomic
def crear_ticket_aplicacion(*, aplicacion, categoria, referencia, solicitante, creado_por, problema, prioridad, enlace=""):
    if not aplicacion.activo:
        raise FlujoError("La aplicación seleccionada no está activa.")
    ticket = Ticket.objects.create(
        ambito=Ticket.Ambito.APLICACION, aplicacion=aplicacion, categoria_app=categoria, referencia=referencia,
        solicitante=solicitante, creado_por=creado_por, problema=problema,
        tipo_soporte=TipoSoporte.APLICACION, prioridad=prioridad,
    )
    registrar(ticket, creado_por, f"Ticket registrado para {aplicacion} ({ticket.get_categoria_app_display().lower()}, "
                                  f"prioridad {ticket.get_prioridad_display().lower()}).")
    destinatarios = list(_administradores()) + ([aplicacion.responsable] if aplicacion.responsable else [])
    transaction.on_commit(lambda: notificar(
        f"Nuevo ticket {ticket.numero} - {aplicacion}",
        f"{solicitante} registró el ticket {ticket.numero} para {aplicacion}.\n\n"
        f"Tipo de solicitud: {ticket.get_categoria_app_display()}\n"
        + (f"Afecta a: {referencia}\n" if referencia else "") + f"\nDetalle: {problema}",
        destinatarios, enlace + ticket_path(ticket) if enlace else "",
    ))
    return ticket


@transaction.atomic
def crear_ticket(*, equipo, solicitante, creado_por, problema, tipo_soporte, prioridad, enlace=""):
    if equipo.estado == Equipo.Estado.BAJA:
        raise FlujoError("No se puede crear un ticket para un equipo dado de baja.")
    abierto = equipo.ticket_abierto
    if abierto:
        raise FlujoError(f"El equipo ya tiene el ticket {abierto.numero} abierto.")
    ticket = Ticket.objects.create(
        equipo=equipo, solicitante=solicitante, creado_por=creado_por,
        problema=problema, tipo_soporte=tipo_soporte, prioridad=prioridad,
    )
    registrar(ticket, creado_por, f"Ticket registrado ({ticket.get_tipo_soporte_display()}, prioridad {ticket.get_prioridad_display().lower()}).")
    transaction.on_commit(lambda: notificar(
        f"Nuevo ticket {ticket.numero}",
        f"{solicitante} registró el ticket {ticket.numero} para el equipo {equipo}.\n\nProblema: {problema}",
        _administradores(), enlace + ticket_path(ticket) if enlace else "",
    ))
    return ticket


def ticket_path(ticket):
    from django.urls import reverse
    return reverse("ticket_detalle", args=[ticket.pk])


@transaction.atomic
def asignar(ticket, *, practicante, tipo_soporte, prioridad, por, enlace=""):
    if ticket.estado not in (Ticket.Estado.PENDIENTE, Ticket.Estado.ASIGNADO, Ticket.Estado.EN_PROCESO):
        raise FlujoError("Solo se pueden asignar tickets pendientes o en atención.")
    anterior = ticket.practicante
    ticket.practicante = practicante
    if not ticket.es_aplicacion:
        ticket.tipo_soporte = tipo_soporte
    ticket.prioridad = prioridad
    ticket.asignado_por = por
    ticket.fecha_asignacion = timezone.now()
    if ticket.estado == Ticket.Estado.PENDIENTE:
        ticket.estado = Ticket.Estado.ASIGNADO
    ticket.save()
    if ticket.equipo_id:
        ticket.equipo.estado = Equipo.Estado.MANTENIMIENTO
        ticket.equipo.save(update_fields=["estado"])
    if anterior and anterior != practicante:
        registrar(ticket, por, f"Ticket reasignado de {anterior} a {practicante}.")
    else:
        registrar(ticket, por, f"Ticket asignado a {practicante} ({ticket.get_tipo_soporte_display()}).")
    url = enlace + ticket_path(ticket) if enlace else ""
    transaction.on_commit(lambda: notificar(
        f"Se le asignó el ticket {ticket.numero}",
        f"Hola {practicante.first_name.title()}, se le asignó el ticket {ticket.numero}.\n\n"
        + (f"Aplicación: {ticket.aplicacion}\nSolicitud: {ticket.get_categoria_app_display()}\n" if ticket.es_aplicacion
           else f"Equipo: {ticket.equipo}\nTipo de soporte: {ticket.get_tipo_soporte_display()}\n")
        + f"Prioridad: {ticket.get_prioridad_display()}\nProblema: {ticket.problema}",
        [practicante], url,
    ))
    return ticket


def _validar_atencion(ticket):
    if not ticket.en_atencion:
        raise FlujoError("El ticket no está en atención (debe estar asignado o en proceso).")


@transaction.atomic
def guardar_diagnostico(ticket, *, datos, por):
    _validar_atencion(ticket)
    existente = ticket.diagnostico_o_none()
    if ticket.es_aplicacion:
        datos = {**datos, "tipo_mantenimiento": Diagnostico.Requiere.APLICACION}
    diag = existente or Diagnostico(ticket=ticket)
    for campo, valor in datos.items():
        setattr(diag, campo, valor)
    diag.realizado_por = por
    diag.fecha = timezone.now()
    diag.save()
    if ticket.estado == Ticket.Estado.ASIGNADO:
        ticket.estado = Ticket.Estado.EN_PROCESO
        ticket.save(update_fields=["estado"])
    if ticket.es_aplicacion:
        registrar(ticket, por, "Análisis del problema actualizado." if existente else "Análisis del problema registrado.")
    else:
        registrar(ticket, por, ("Diagnóstico actualizado" if existente else "Diagnóstico registrado")
                  + f": requiere {diag.get_tipo_mantenimiento_display().lower()}.")
    return diag


@transaction.atomic
def registrar_mantenimiento(ticket, *, datos, por):
    _validar_atencion(ticket)
    if not ticket.diagnostico_o_none():
        raise FlujoError("Primero registre el análisis del problema." if ticket.es_aplicacion else "Primero registre el diagnóstico del equipo.")
    if ticket.es_aplicacion:
        datos = {**datos, "tipo": Mantenimiento.Tipo.APLICACION}
    mant = Mantenimiento.objects.create(ticket=ticket, realizado_por=por, **datos)
    if ticket.estado == Ticket.Estado.ASIGNADO:
        ticket.estado = Ticket.Estado.EN_PROCESO
        ticket.save(update_fields=["estado"])
    registrar(ticket, por, "Acción realizada en la aplicación registrada." if ticket.es_aplicacion
              else f"Mantenimiento {mant.get_tipo_display().lower()} registrado.")
    return mant


@transaction.atomic
def registrar_resultado(ticket, *, resultado, detalle, por, enlace=""):
    _validar_atencion(ticket)
    diag = ticket.diagnostico_o_none()
    if resultado not in ticket.resultados_validos:
        raise FlujoError("El resultado no corresponde al tipo de ticket.")
    if not diag:
        raise FlujoError("Primero registre el análisis del problema." if ticket.es_aplicacion else "Primero registre el diagnóstico del equipo.")
    if resultado == Ticket.Resultado.RESUELTO and not ticket.mantenimientos.exists():
        raise FlujoError("Para marcar la solicitud como resuelta registre las acciones realizadas.")
    if (
        resultado == Ticket.Resultado.REPARADO
        and diag.tipo_mantenimiento != Diagnostico.Requiere.NINGUNO
        and not ticket.mantenimientos.exists()
    ):
        raise FlujoError("Para marcar el equipo como reparado registre el mantenimiento realizado.")
    ticket.resultado = resultado
    ticket.detalle_resultado = detalle
    ticket.fecha_atencion = timezone.now()
    ticket.estado = Ticket.Estado.ATENDIDO
    ticket.save()
    if ticket.equipo_id:
        ticket.equipo.estado = Ticket.ESTADO_EQUIPO_POR_RESULTADO[resultado]
        ticket.equipo.save(update_fields=["estado"])
    registrar(ticket, por, f"Soporte atendido. Resultado: {ticket.get_resultado_display()}.")
    url = enlace + ticket_path(ticket) if enlace else ""
    if ticket.es_aplicacion:
        cuerpo = (f"Su solicitud {ticket.numero} sobre {ticket.aplicacion} fue atendida.\n\n"
                  f"Resultado: {ticket.get_resultado_display()}\nDetalle: {detalle}")
    else:
        cuerpo = (f"Su ticket {ticket.numero} fue atendido.\n\nEquipo: {ticket.equipo}\nResultado: {ticket.get_resultado_display()}\n"
                  f"Detalle: {detalle}\n\nAcérquese al {settings.DEPARTAMENTO_TIC} para retirar su equipo.")
    transaction.on_commit(lambda: notificar(f"Ticket {ticket.numero} atendido", cuerpo, [ticket.solicitante], url))
    return ticket


@transaction.atomic
def cerrar(ticket, *, por, comentario=""):
    if ticket.estado != Ticket.Estado.ATENDIDO:
        raise FlujoError("Solo se pueden cerrar tickets atendidos.")
    ticket.estado = Ticket.Estado.CERRADO
    ticket.fecha_cierre = timezone.now()
    ticket.cerrado_por = por
    ticket.save()
    registrar(ticket, por, "Ticket cerrado." + (f" {comentario}" if comentario else ""))
    return ticket


@transaction.atomic
def cambiar_estado(ticket, *, estado, motivo, por):
    """Cambio manual del estado por el Administrador (p. ej. reabrir un ticket)."""
    if estado == ticket.estado:
        raise FlujoError("El ticket ya está en ese estado.")
    if estado in (Ticket.Estado.ASIGNADO, Ticket.Estado.EN_PROCESO) and not ticket.practicante:
        raise FlujoError("Asigne primero un practicante al ticket.")
    if estado == Ticket.Estado.ATENDIDO and not ticket.resultado:
        raise FlujoError("Para marcarlo como atendido registre el resultado del soporte.")
    if ticket.estado == Ticket.Estado.CERRADO and ticket.equipo_id:
        otro = ticket.equipo.tickets.exclude(pk=ticket.pk).exclude(estado=Ticket.Estado.CERRADO).first()
        if otro:
            raise FlujoError(f"No se puede reabrir: el equipo ya tiene el ticket {otro.numero} abierto.")
    anterior = ticket.get_estado_display()
    ticket.estado = estado
    if estado == Ticket.Estado.CERRADO:
        ticket.fecha_cierre = timezone.now()
        ticket.cerrado_por = por
    else:
        ticket.fecha_cierre = None
        ticket.cerrado_por = None
    if estado in (Ticket.Estado.PENDIENTE, Ticket.Estado.ASIGNADO, Ticket.Estado.EN_PROCESO):
        ticket.resultado = ""
        ticket.fecha_atencion = None
        if ticket.equipo_id and ticket.equipo.estado != Equipo.Estado.BAJA:
            ticket.equipo.estado = Equipo.Estado.MANTENIMIENTO if estado != Ticket.Estado.PENDIENTE else Equipo.Estado.ACTIVO
            ticket.equipo.save(update_fields=["estado"])
    if estado == Ticket.Estado.PENDIENTE:
        ticket.practicante = None
    ticket.save()
    registrar(ticket, por, f"Estado cambiado de {anterior} a {ticket.get_estado_display()}. Motivo: {motivo}")
    return ticket
