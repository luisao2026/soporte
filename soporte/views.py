from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.forms import modelform_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from aplicaciones.models import Aplicacion
from cuentas.forms import FormBootstrap
from cuentas.models import Usuario
from cuentas.utils import paginar
from equipos.models import Equipo

from . import servicios
from .forms import (AccionAppForm, AnalisisAppForm, AsignarForm, CambiarEstadoForm, CerrarForm, DiagnosticoForm,
                    FiltroTicketForm, MantenimientoForm, ObservacionForm, ResultadoForm, TicketAplicacionForm, TicketForm)
from .models import CategoriaApp, Diagnostico, Mantenimiento, Observacion, Ticket, TipoSoporte

Estado = Ticket.Estado


# ---------------- Permisos ----------------

def tickets_visibles(u):
    qs = Ticket.objects.select_related("equipo", "equipo__categoria", "aplicacion", "solicitante", "practicante")
    if u.es_personal_tic:
        return qs
    if u.es_practicante:
        return qs.filter(practicante=u)
    return qs.filter(solicitante=u)


def permisos(u, t):
    es_su_practicante = u.es_practicante and t.practicante_id == u.pk
    return {
        "atender": t.en_atencion and (u.es_admin or es_su_practicante),
        "asignar": u.es_admin and t.estado in (Estado.PENDIENTE, Estado.ASIGNADO, Estado.EN_PROCESO),
        "cerrar": u.es_personal_tic and t.estado == Estado.ATENDIDO,
        "observar": t.esta_abierto and (u.es_personal_tic or es_su_practicante),
        "cambiar_estado": u.es_admin,
        "editar": t.estado == Estado.PENDIENTE and (u.es_admin or t.solicitante_id == u.pk),
    }


def _ticket(request, pk):
    try:
        return tickets_visibles(request.user).get(pk=pk)
    except Ticket.DoesNotExist:
        raise Http404


def _base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


# ---------------- Panel de inicio ----------------

@login_required
def inicio(request):
    u = request.user
    ctx = {}
    if u.es_personal_tic:
        por_estado = dict(Ticket.objects.values_list("estado").annotate(n=Count("id")))
        plural = {"PENDIENTE": "Pendientes", "ASIGNADO": "Asignados", "EN_PROCESO": "En proceso", "ATENDIDO": "Atendidos", "CERRADO": "Cerrados"}
        ctx["tarjetas"] = [(v, f"Tickets {plural[v].lower()}", por_estado.get(v, 0), Ticket.COLOR_ESTADO[v]) for v, _ in Estado.choices]
        ctx["sin_asignar"] = Ticket.objects.filter(estado=Estado.PENDIENTE).select_related("equipo", "aplicacion", "solicitante").order_by("fecha")[:8]
        ctx["por_atender"] = Ticket.objects.filter(estado=Estado.ATENDIDO).select_related("equipo", "aplicacion", "practicante").order_by("fecha_atencion")[:8]
        ctx["aplicaciones"] = Aplicacion.objects.filter(activo=True).annotate(
            abiertos=Count("tickets", filter=Q(tickets__estado__in=[Estado.PENDIENTE, Estado.ASIGNADO, Estado.EN_PROCESO, Estado.ATENDIDO])),
            total=Count("tickets"),
        )
        eq = dict(Equipo.objects.values_list("estado").annotate(n=Count("id")))
        ctx["equipos_estado"] = [(l, eq.get(v, 0), Equipo.COLOR_ESTADO[v]) for v, l in Equipo.Estado.choices]
        ctx["total_equipos"] = sum(eq.values())
        ctx["carga"] = Usuario.objects.filter(rol=Usuario.Rol.PRACTICANTE, is_active=True).annotate(
            activos=Count("tickets_asignados", filter=Q(tickets_asignados__estado__in=[Estado.ASIGNADO, Estado.EN_PROCESO])),
            atendidos=Count("tickets_asignados", filter=Q(tickets_asignados__estado__in=[Estado.ATENDIDO, Estado.CERRADO])),
        )
        ctx["usuarios_activos"] = Usuario.objects.filter(is_active=True).count()
    elif u.es_practicante:
        mios = Ticket.objects.filter(practicante=u)
        ctx["mis_activos"] = mios.filter(estado__in=[Estado.ASIGNADO, Estado.EN_PROCESO]).select_related("equipo", "aplicacion", "solicitante").order_by("fecha")
        ctx["resumen"] = [
            ("Asignados", mios.filter(estado=Estado.ASIGNADO).count(), "info"),
            ("En proceso", mios.filter(estado=Estado.EN_PROCESO).count(), "warning"),
            ("Atendidos", mios.filter(estado=Estado.ATENDIDO).count(), "primary"),
            ("Cerrados", mios.filter(estado=Estado.CERRADO).count(), "success"),
        ]
        ctx["diagnosticos"] = Diagnostico.objects.filter(realizado_por=u).count()
        ctx["mantenimientos"] = Mantenimiento.objects.filter(realizado_por=u).count()
    else:
        ctx["mis_equipos"] = u.equipos.select_related("categoria", "marca", "modelo")
        ctx["mis_tickets"] = u.tickets_solicitados.select_related("equipo", "aplicacion", "practicante")[:8]
        ctx["abiertos"] = u.tickets_solicitados.exclude(estado=Estado.CERRADO).count()
    return render(request, "inicio.html", ctx)


# ---------------- Tickets ----------------

@login_required
def ticket_lista(request):
    u = request.user
    tickets = tickets_visibles(u)
    form = FiltroTicketForm(request.GET or None)
    if not u.es_personal_tic:
        del form.fields["practicante"]
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            q = d["q"]
            tickets = tickets.filter(
                Q(numero__icontains=q) | Q(equipo__codigo__icontains=q) | Q(equipo__nombre__icontains=q)
                | Q(aplicacion__nombre__icontains=q) | Q(referencia__icontains=q)
                | Q(numero_serie__icontains=q) | Q(solicitante__first_name__icontains=q) | Q(solicitante__last_name__icontains=q)
            )
        if d["ambito"]:
            tickets = tickets.filter(ambito=d["ambito"])
        if d["estado"]:
            tickets = tickets.filter(estado=d["estado"])
        if d["tipo"]:
            tickets = tickets.filter(tipo_soporte=d["tipo"])
        if d["prioridad"]:
            tickets = tickets.filter(prioridad=d["prioridad"])
        if d.get("practicante"):
            tickets = tickets.filter(practicante=d["practicante"])
    pagina, filtros = paginar(request, tickets)
    titulo = "Tickets asignados" if u.es_practicante else ("Tickets de soporte" if u.es_personal_tic else "Mis tickets")
    return render(request, "soporte/ticket_lista.html", {"pagina": pagina, "filtros": filtros, "form": form, "titulo": titulo})


@login_required
def ticket_crear(request):
    """Primero se elige si el soporte es para un equipo o para una aplicación."""
    u = request.user
    if not u.puede_crear_tickets:
        raise PermissionDenied("Su rol no puede crear tickets.")
    tipo = request.GET.get("tipo") or ("equipo" if request.GET.get("equipo") or "equipo" in request.POST else "")
    if not tipo and "aplicacion" in request.POST:
        tipo = "aplicacion"
    if tipo == "aplicacion":
        return _crear_ticket_aplicacion(request)
    if tipo != "equipo":
        return render(request, "soporte/ticket_elegir.html", {
            "aplicaciones": Aplicacion.objects.filter(activo=True),
            "tiene_equipos": u.es_admin or u.equipos.exists(),
        })
    inicial = {"equipo": request.GET.get("equipo")} if request.GET.get("equipo") else {}
    form = TicketForm(request.POST or None, usuario=u, initial=inicial)
    if not form.fields["equipo"].queryset.exists() and request.method == "GET":
        messages.info(request, "No tiene equipos disponibles para soporte. Registre un equipo primero (o el equipo ya tiene un ticket abierto).")
    if form.is_valid():
        d = form.cleaned_data
        equipo = d["equipo"]
        solicitante = d.get("solicitante") or (equipo.responsable if u.es_admin else u)
        try:
            ticket = servicios.crear_ticket(
                equipo=equipo, solicitante=solicitante, creado_por=u, problema=d["problema"],
                tipo_soporte=d["tipo_soporte"], prioridad=d["prioridad"], enlace=_base_url(request),
            )
        except servicios.FlujoError as e:
            form.add_error("equipo", str(e))
        else:
            messages.success(request, f"Ticket {ticket.numero} registrado. El Departamento de TIC lo asignará a un técnico.")
            return redirect("ticket_detalle", pk=ticket.pk)
    return render(request, "soporte/ticket_form.html", {"form": form, "titulo": "Soporte para un equipo informático", "ambito": "equipo"})


def _crear_ticket_aplicacion(request):
    u = request.user
    inicial = {"aplicacion": request.GET.get("aplicacion")} if request.GET.get("aplicacion") else {}
    form = TicketAplicacionForm(request.POST or None, usuario=u, initial=inicial)
    if form.is_valid():
        d = form.cleaned_data
        try:
            ticket = servicios.crear_ticket_aplicacion(
                aplicacion=d["aplicacion"], categoria=d["categoria_app"], referencia=d["referencia"],
                solicitante=d.get("solicitante") or u, creado_por=u, problema=d["problema"],
                prioridad=d["prioridad"], enlace=_base_url(request),
            )
        except servicios.FlujoError as e:
            form.add_error("aplicacion", str(e))
        else:
            messages.success(request, f"Ticket {ticket.numero} registrado. El Departamento de TIC lo asignará a un técnico.")
            return redirect("ticket_detalle", pk=ticket.pk)
    return render(request, "soporte/ticket_form.html", {"form": form, "titulo": "Soporte para una aplicación", "ambito": "aplicacion"})


class TicketEditarForm(FormBootstrap, modelform_factory(Ticket, fields=["problema", "tipo_soporte", "prioridad"])):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import TIPOS_EQUIPO
        self.fields["tipo_soporte"].choices = TIPOS_EQUIPO


class TicketAppEditarForm(FormBootstrap, modelform_factory(Ticket, fields=["categoria_app", "referencia", "problema", "prioridad"],
                                                            labels={"problema": "Detalle de la solicitud"})):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria_app"].required = True
        self.fields["categoria_app"].choices = list(CategoriaApp.choices)


@login_required
def ticket_editar(request, pk):
    ticket = _ticket(request, pk)
    if not permisos(request.user, ticket)["editar"]:
        raise PermissionDenied("Solo puede modificar tickets pendientes.")
    clase = TicketAppEditarForm if ticket.es_aplicacion else TicketEditarForm
    form = clase(request.POST or None, instance=ticket)
    if form.is_valid():
        form.save()
        servicios.registrar(ticket, request.user, "Datos del ticket modificados.")
        messages.success(request, "Ticket actualizado.")
        return redirect("ticket_detalle", pk=ticket.pk)
    return render(request, "soporte/ticket_form.html", {"form": form, "titulo": f"Modificar ticket {ticket.numero}", "ticket": ticket})


@login_required
def ticket_detalle(request, pk):
    ticket = _ticket(request, pk)
    p = permisos(request.user, ticket)
    diag = ticket.diagnostico_o_none()
    hay_mant = ticket.mantenimientos.exists()
    app = ticket.es_aplicacion
    hechos = [
        ("Registro", True),
        ("Asignación", bool(ticket.practicante_id)),
        ("Análisis" if app else "Diagnóstico", bool(diag)),
        ("Acciones" if app else "Mantenimiento",
         hay_mant or bool(ticket.resultado) or (diag and diag.tipo_mantenimiento == Diagnostico.Requiere.NINGUNO)),
        ("Resultado", bool(ticket.resultado)),
        ("Cierre", ticket.estado == Estado.CERRADO),
    ]
    actual = next((i for i, (_, h) in enumerate(hechos) if not h), None)
    pasos = [(n, h, i == actual) for i, (n, h) in enumerate(hechos)]
    ctx = {
        "t": ticket, "p": p, "diag": diag, "pasos": pasos,
        "mantenimientos": ticket.mantenimientos.select_related("realizado_por"),
        "observaciones": ticket.observaciones.select_related("autor"),
        "historial": ticket.historial.select_related("usuario"),
    }
    if p["asignar"]:
        ctx["form_asignar"] = AsignarForm(instance=ticket, prefix="asg")
    if p["atender"] and app:
        ctx["form_diag"] = AnalisisAppForm(instance=diag, prefix="diag")
        ctx["form_mant"] = AccionAppForm(prefix="mant")
        ctx["form_res"] = ResultadoForm(instance=ticket, prefix="res")
    elif p["atender"]:
        ctx["form_diag"] = DiagnosticoForm(instance=diag, prefix="diag")
        inicial_tipo = diag.tipo_mantenimiento if diag and diag.tipo_mantenimiento in Mantenimiento.Tipo.values else (
            ticket.tipo_soporte if ticket.tipo_soporte in Mantenimiento.Tipo.values else None)
        ctx["form_mant"] = MantenimientoForm(prefix="mant", initial={"tipo": inicial_tipo})
        ctx["form_res"] = ResultadoForm(instance=ticket, prefix="res")
    if p["observar"]:
        ctx["form_obs"] = ObservacionForm(prefix="obs")
    if p["cerrar"]:
        ctx["form_cerrar"] = CerrarForm(prefix="cer")
    if p["cambiar_estado"]:
        ctx["form_estado"] = CambiarEstadoForm(prefix="est", initial={"estado": ticket.estado})
    return render(request, "soporte/ticket_detalle.html", ctx)


def _accion(request, pk, permiso, form_class, prefix, ejecutar, exito, instance_attr=None):
    """Procesa un formulario de acción del ticket y vuelve al detalle."""
    ticket = _ticket(request, pk)
    if not permisos(request.user, ticket)[permiso]:
        raise PermissionDenied("No puede realizar esta acción sobre el ticket.")
    kwargs = {"prefix": prefix}
    if instance_attr == "ticket":
        kwargs["instance"] = ticket
    if isinstance(form_class, tuple):  # (formulario para equipos, formulario para aplicaciones)
        form_class = form_class[1] if ticket.es_aplicacion else form_class[0]
    form = form_class(request.POST, **kwargs)
    if form.is_valid():
        try:
            ejecutar(ticket, form.cleaned_data)
            messages.success(request, exito)
        except servicios.FlujoError as e:
            messages.error(request, str(e))
            if instance_attr == "ticket":
                ticket.refresh_from_db()
    else:
        errores = "; ".join(f"{form.fields[c].label if c in form.fields else ''}: {' '.join(e)}".strip(": ") for c, e in form.errors.items())
        messages.error(request, f"Revise los datos: {errores}")
    return redirect("ticket_detalle", pk=pk)


@require_POST
@login_required
def ticket_asignar(request, pk):
    def ejecutar(t, d):
        servicios.asignar(t, practicante=d["practicante"], tipo_soporte=d.get("tipo_soporte", t.tipo_soporte), prioridad=d["prioridad"],
                          por=request.user, enlace=_base_url(request))
    return _accion(request, pk, "asignar", AsignarForm, "asg", ejecutar, "Ticket asignado al practicante.", "ticket")


@require_POST
@login_required
def ticket_diagnostico(request, pk):
    def ejecutar(t, d):
        servicios.guardar_diagnostico(t, datos=d, por=request.user)
    return _accion(request, pk, "atender", (DiagnosticoForm, AnalisisAppForm), "diag", ejecutar, "Análisis / diagnóstico guardado.")


@require_POST
@login_required
def ticket_mantenimiento(request, pk):
    def ejecutar(t, d):
        servicios.registrar_mantenimiento(t, datos=d, por=request.user)
    return _accion(request, pk, "atender", (MantenimientoForm, AccionAppForm), "mant", ejecutar, "Trabajo registrado.")


@require_POST
@login_required
def ticket_resultado(request, pk):
    def ejecutar(t, d):
        servicios.registrar_resultado(t, resultado=d["resultado"], detalle=d["detalle_resultado"], por=request.user, enlace=_base_url(request))
    return _accion(request, pk, "atender", ResultadoForm, "res", ejecutar, "Resultado registrado. Se notificó al solicitante.", "ticket")


@require_POST
@login_required
def ticket_observacion(request, pk):
    def ejecutar(t, d):
        Observacion.objects.create(ticket=t, autor=request.user, texto=d["texto"])
        servicios.registrar(t, request.user, "Observación registrada.")
    return _accion(request, pk, "observar", ObservacionForm, "obs", ejecutar, "Observación registrada.")


@require_POST
@login_required
def ticket_cerrar(request, pk):
    def ejecutar(t, d):
        servicios.cerrar(t, por=request.user, comentario=d["comentario"])
    return _accion(request, pk, "cerrar", CerrarForm, "cer", ejecutar, "Ticket cerrado.")


@require_POST
@login_required
def ticket_cambiar_estado(request, pk):
    def ejecutar(t, d):
        servicios.cambiar_estado(t, estado=d["estado"], motivo=d["motivo"], por=request.user)
    return _accion(request, pk, "cambiar_estado", CambiarEstadoForm, "est", ejecutar, "Estado del ticket actualizado.")


@login_required
def ticket_pdf(request, pk):
    from .pdf import pdf_ticket
    return pdf_ticket(_ticket(request, pk))
