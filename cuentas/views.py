from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import rol_requerido
from .forms import CambiarClaveForm, LoginForm, PerfilForm, UsuarioForm
from .models import Usuario
from .utils import paginar

ADMIN = Usuario.Rol.ADMIN


class Login(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


# ---------------- Administración de usuarios (solo Administrador) ----------------

@rol_requerido(ADMIN)
def usuario_lista(request):
    usuarios = Usuario.objects.all()
    q = request.GET.get("q", "").strip()
    rol = request.GET.get("rol", "")
    estado = request.GET.get("estado", "")
    if q:
        usuarios = usuarios.filter(
            Q(cedula__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(username__icontains=q)
        )
    if rol:
        usuarios = usuarios.filter(rol=rol)
    if estado in ("1", "0"):
        usuarios = usuarios.filter(is_active=estado == "1")
    pagina, filtros = paginar(request, usuarios)
    return render(request, "cuentas/usuario_lista.html", {
        "pagina": pagina, "filtros": filtros, "roles": Usuario.Rol.choices, "q": q, "rol": rol, "estado": estado,
    })


@rol_requerido(ADMIN)
def usuario_crear(request):
    rol_inicial = request.GET.get("rol") if request.GET.get("rol") in Usuario.Rol.values else Usuario.Rol.ESTUDIANTE
    form = UsuarioForm(request.POST or None, initial={"rol": rol_inicial, "is_active": True})
    if form.is_valid():
        usuario = form.save()
        messages.success(request, f"Usuario {usuario} registrado. Usuario y contraseña inicial: su cédula ({usuario.cedula}).")
        return redirect("usuario_lista")
    titulo = f"Registrar {dict(Usuario.Rol.choices)[rol_inicial].lower()}"
    return render(request, "cuentas/usuario_form.html", {"form": form, "titulo": titulo})


@rol_requerido(ADMIN)
def usuario_editar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    form = UsuarioForm(request.POST or None, instance=usuario)
    if form.is_valid():
        if usuario == request.user and not form.cleaned_data["is_active"]:
            messages.error(request, "No puede desactivar su propio usuario.")
        else:
            form.save()
            messages.success(request, "Información del usuario actualizada.")
            return redirect("usuario_lista")
    return render(request, "cuentas/usuario_form.html", {"form": form, "titulo": f"Modificar usuario: {usuario}", "usuario": usuario})


@rol_requerido(ADMIN)
def usuario_detalle(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    return render(request, "cuentas/usuario_detalle.html", {
        "u": usuario,
        "equipos": usuario.equipos.select_related("categoria", "marca", "modelo"),
        "tickets": usuario.tickets_solicitados.select_related("equipo")[:10],
        "asignados": usuario.tickets_asignados.select_related("equipo")[:10],
    })


@require_POST
@rol_requerido(ADMIN)
def usuario_cambiar_estado(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario == request.user:
        messages.error(request, "No puede desactivar su propio usuario.")
    else:
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        messages.success(request, f"Usuario {usuario} {'activado' if usuario.is_active else 'desactivado'}.")
    return redirect(request.POST.get("next") or "usuario_lista")


@require_POST
@rol_requerido(ADMIN)
def usuario_restablecer_clave(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if not usuario.cedula:
        messages.error(request, "El usuario no tiene cédula registrada.")
    else:
        usuario.set_password(usuario.cedula)
        usuario.save(update_fields=["password"])
        messages.success(request, f"La contraseña de {usuario} ahora es su cédula ({usuario.cedula}).")
    return redirect("usuario_detalle", pk=pk)


# ---------------- Perfil del usuario ----------------

@login_required
def perfil(request):
    form = PerfilForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Sus datos fueron actualizados.")
        return redirect("perfil")
    return render(request, "cuentas/perfil.html", {"form": form})


@login_required
def cambiar_clave(request):
    form = CambiarClaveForm(request.user, request.POST or None)
    if form.is_valid():
        usuario = form.save()
        update_session_auth_hash(request, usuario)
        messages.success(request, "Contraseña actualizada correctamente.")
        return redirect("perfil")
    return render(request, "cuentas/cambiar_clave.html", {"form": form})
