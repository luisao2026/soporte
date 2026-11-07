from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cuentas.decorators import rol_requerido
from cuentas.models import Usuario
from cuentas.utils import paginar

from .forms import CategoriaForm, EquipoForm, MarcaForm, ModeloForm
from .models import Categoria, Equipo, Marca, Modelo


def equipos_visibles(usuario):
    """Administrador, Responsable de TIC y practicantes ven todo el inventario; docentes y estudiantes, solo sus equipos."""
    qs = Equipo.objects.select_related("categoria", "marca", "modelo", "responsable")
    if usuario.es_personal_tic or usuario.es_practicante:
        return qs
    return qs.filter(responsable=usuario)


def puede_editar(usuario, equipo):
    return usuario.es_admin or (usuario.es_solicitante and equipo.responsable_id == usuario.pk and equipo.estado != Equipo.Estado.BAJA)


def _modelos_json():
    return list(Modelo.objects.filter(activo=True).values("id", "nombre", "marca_id"))


@login_required
def equipo_lista(request):
    u = request.user
    if not (u.es_personal_tic or u.es_practicante or u.es_solicitante):
        raise PermissionDenied
    equipos = equipos_visibles(u)
    f = {k: request.GET.get(k, "").strip() for k in ("q", "categoria", "marca", "estado")}
    if f["q"]:
        equipos = equipos.filter(
            Q(codigo__icontains=f["q"]) | Q(nombre__icontains=f["q"]) | Q(numero_serie__icontains=f["q"])
            | Q(responsable__first_name__icontains=f["q"]) | Q(responsable__last_name__icontains=f["q"])
        )
    if f["categoria"]:
        equipos = equipos.filter(categoria_id=f["categoria"])
    if f["marca"]:
        equipos = equipos.filter(marca_id=f["marca"])
    if f["estado"]:
        equipos = equipos.filter(estado=f["estado"])
    pagina, filtros = paginar(request, equipos)
    return render(request, "equipos/equipo_lista.html", {
        "pagina": pagina, "filtros": filtros, "f": f,
        "categorias": Categoria.objects.all(), "marcas": Marca.objects.all(), "estados": Equipo.Estado.choices,
        "puede_registrar": u.es_admin or u.es_solicitante,
    })


@login_required
def equipo_crear(request):
    u = request.user
    if not (u.es_admin or u.es_solicitante):
        raise PermissionDenied
    inicial = {}
    if u.es_admin and request.GET.get("responsable"):
        inicial["responsable"] = request.GET["responsable"]
    form = EquipoForm(request.POST or None, usuario=u, initial=inicial)
    if form.is_valid():
        equipo = form.save(commit=False)
        if not u.es_admin:
            equipo.responsable = u
            equipo.estado = Equipo.Estado.ACTIVO
        equipo.registrado_por = u
        equipo.save()
        messages.success(request, f"Equipo {equipo.codigo} registrado correctamente.")
        return redirect("equipo_detalle", pk=equipo.pk)
    return render(request, "equipos/equipo_form.html", {"form": form, "titulo": "Registrar equipo", "modelos_json": _modelos_json()})


@login_required
def equipo_editar(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    if not puede_editar(request.user, equipo):
        raise PermissionDenied
    form = EquipoForm(request.POST or None, instance=equipo, usuario=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Equipo actualizado.")
        return redirect("equipo_detalle", pk=equipo.pk)
    return render(request, "equipos/equipo_form.html", {
        "form": form, "titulo": f"Modificar equipo {equipo.codigo}", "equipo": equipo, "modelos_json": _modelos_json(),
    })


@login_required
def equipo_detalle(request, pk):
    try:
        equipo = equipos_visibles(request.user).get(pk=pk)
    except Equipo.DoesNotExist:
        raise Http404
    tickets = equipo.tickets.select_related("practicante").prefetch_related("mantenimientos")
    return render(request, "equipos/equipo_detalle.html", {
        "equipo": equipo, "tickets": tickets,
        "puede_editar": puede_editar(request.user, equipo),
        "puede_ticket": request.user.puede_crear_tickets and not equipo.ticket_abierto and equipo.estado != Equipo.Estado.BAJA
        and (request.user.es_admin or equipo.responsable_id == request.user.pk),
    })


# ---------------- Catálogos: categorías, marcas y modelos (Administrador) ----------------

CATALOGOS = {
    "categoria": (Categoria, CategoriaForm, "categoría"),
    "marca": (Marca, MarcaForm, "marca"),
    "modelo": (Modelo, ModeloForm, "modelo"),
}


@rol_requerido(Usuario.Rol.ADMIN)
def catalogos(request):
    forms_ = {k: v[1](prefix=k) for k, v in CATALOGOS.items()}
    if request.method == "POST":
        tipo = request.POST.get("tipo")
        if tipo in CATALOGOS:
            form = CATALOGOS[tipo][1](request.POST, prefix=tipo)
            if form.is_valid():
                obj = form.save()
                messages.success(request, f"Se registró {CATALOGOS[tipo][2]}: {obj}.")
                return redirect(f"{request.path}#{tipo}")
            forms_[tipo] = form
    return render(request, "equipos/catalogos.html", {
        "forms": forms_,
        "categorias": Categoria.objects.annotate(total=Count("equipos")),
        "marcas": Marca.objects.annotate(total=Count("equipos"), n_modelos=Count("modelos", distinct=True)),
        "modelos": Modelo.objects.select_related("marca").annotate(total=Count("equipos")),
    })


@rol_requerido(Usuario.Rol.ADMIN)
def catalogo_editar(request, tipo, pk):
    if tipo not in CATALOGOS:
        raise Http404
    modelo, form_class, nombre = CATALOGOS[tipo]
    obj = get_object_or_404(modelo, pk=pk)
    form = form_class(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, "Registro actualizado.")
        return redirect(f"/equipos/catalogos/#{tipo}")
    return render(request, "equipos/catalogo_form.html", {"form": form, "titulo": f"Modificar {nombre}: {obj}"})


@require_POST
@rol_requerido(Usuario.Rol.ADMIN)
def catalogo_estado(request, tipo, pk):
    if tipo not in CATALOGOS:
        raise Http404
    obj = get_object_or_404(CATALOGOS[tipo][0], pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    return redirect(f"/equipos/catalogos/#{tipo}")
