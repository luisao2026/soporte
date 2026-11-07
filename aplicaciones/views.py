from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cuentas.decorators import rol_requerido
from cuentas.models import Usuario
from soporte.models import CategoriaApp, Ticket

from .forms import AplicacionForm
from .models import Aplicacion

ABIERTOS = [Ticket.Estado.PENDIENTE, Ticket.Estado.ASIGNADO, Ticket.Estado.EN_PROCESO, Ticket.Estado.ATENDIDO]


def _puede_ver(u):
    return u.es_personal_tic or u.es_practicante


@login_required
def aplicacion_lista(request):
    if not _puede_ver(request.user):
        raise PermissionDenied
    aplicaciones = Aplicacion.objects.select_related("responsable").annotate(
        abiertos=Count("tickets", filter=Q(tickets__estado__in=ABIERTOS)),
        total=Count("tickets"),
    )
    return render(request, "aplicaciones/lista.html", {"aplicaciones": aplicaciones})


@login_required
def aplicacion_detalle(request, pk):
    if not _puede_ver(request.user):
        raise PermissionDenied
    app = get_object_or_404(Aplicacion.objects.select_related("responsable"), pk=pk)
    tickets = app.tickets.select_related("solicitante", "practicante")
    if request.user.es_practicante:
        tickets = tickets.filter(practicante=request.user)
    por_categoria = dict(app.tickets.values_list("categoria_app").annotate(n=Count("id")))
    categorias = [(l, por_categoria.get(v, 0)) for v, l in CategoriaApp.choices if por_categoria.get(v)]
    return render(request, "aplicaciones/detalle.html", {
        "app": app, "tickets": tickets[:50], "categorias": categorias,
        "abiertos": app.tickets.filter(estado__in=ABIERTOS).count(), "total": app.tickets.count(),
    })


@rol_requerido(Usuario.Rol.ADMIN)
def aplicacion_crear(request):
    form = AplicacionForm(request.POST or None, initial={"activo": True})
    if form.is_valid():
        app = form.save()
        messages.success(request, f"Aplicación «{app}» registrada.")
        return redirect("aplicacion_lista")
    return render(request, "aplicaciones/form.html", {"form": form, "titulo": "Registrar aplicación"})


@rol_requerido(Usuario.Rol.ADMIN)
def aplicacion_editar(request, pk):
    app = get_object_or_404(Aplicacion, pk=pk)
    form = AplicacionForm(request.POST or None, instance=app)
    if form.is_valid():
        form.save()
        messages.success(request, "Aplicación actualizada.")
        return redirect("aplicacion_detalle", pk=app.pk)
    return render(request, "aplicaciones/form.html", {"form": form, "titulo": f"Modificar: {app}", "app": app})


@require_POST
@rol_requerido(Usuario.Rol.ADMIN)
def aplicacion_estado(request, pk):
    app = get_object_or_404(Aplicacion, pk=pk)
    app.activo = not app.activo
    app.save(update_fields=["activo"])
    messages.success(request, f"Aplicación «{app}» {'activada' if app.activo else 'desactivada'}.")
    return redirect(request.POST.get("next") or "aplicacion_lista")
