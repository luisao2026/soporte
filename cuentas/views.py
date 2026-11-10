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


# ---------------- Carga masiva de usuarios (solo Administrador) ----------------

from django.http import HttpResponse  # noqa: E402

from . import importar  # noqa: E402

SESION_IMPORTAR = "importacion_usuarios"


@rol_requerido(ADMIN)
def usuario_plantilla(request):
    resp = HttpResponse(importar.plantilla_excel(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="plantilla_usuarios.xlsx"'
    return resp


@rol_requerido(ADMIN)
def usuario_importar(request):
    roles = [(v, l) for v, l in Usuario.Rol.choices]
    ctx = {"roles": roles, "rol_defecto": "", "actualizar": False}

    if request.method == "POST" and request.POST.get("accion") == "confirmar":
        datos = request.session.get(SESION_IMPORTAR)
        if not datos:
            messages.error(request, "La vista previa expiró. Vuelva a subir el archivo.")
            return redirect("usuario_importar")
        creados, actualizados = importar.aplicar(datos["resultado"])
        del request.session[SESION_IMPORTAR]
        partes = [f"{creados} usuario{'s' if creados != 1 else ''} creado{'s' if creados != 1 else ''}"]
        if actualizados:
            partes.append(f"{actualizados} actualizado{'s' if actualizados != 1 else ''}")
        messages.success(request, "Carga masiva terminada: " + ", ".join(partes) +
                         ". Cada usuario nuevo ingresa con su cédula como usuario y contraseña.")
        return redirect("usuario_lista")

    if request.method == "POST":
        archivo = request.FILES.get("archivo")
        rol_defecto = request.POST.get("rol_defecto", "")
        rol_defecto = rol_defecto if rol_defecto in Usuario.Rol.values else ""
        actualizar = request.POST.get("actualizar") == "on"
        ctx.update(rol_defecto=rol_defecto, actualizar=actualizar)
        if not archivo:
            messages.error(request, "Seleccione el archivo de Excel o CSV.")
            return render(request, "cuentas/usuario_importar.html", ctx)
        if archivo.size > 5 * 1024 * 1024:
            messages.error(request, "El archivo supera los 5 MB.")
            return render(request, "cuentas/usuario_importar.html", ctx)
        try:
            filas = importar.leer_archivo(archivo)
        except importar.ArchivoInvalido as e:
            messages.error(request, str(e))
            return render(request, "cuentas/usuario_importar.html", ctx)
        resultado = importar.validar(filas, rol_defecto=rol_defecto, actualizar=actualizar)
        request.session[SESION_IMPORTAR] = {"resultado": resultado, "archivo": archivo.name}
        orden = {"error": 0, "crear": 1, "actualizar": 2, "omitir": 3}
        ctx.update(
            archivo=archivo.name, total=importar.resumen(resultado), n_filas=len(resultado),
            filas=[{**r, "rol_txt": dict(Usuario.Rol.choices).get(r["datos"]["rol"], ""),
                     "genero_txt": dict(Usuario.Genero.choices).get(r["datos"]["genero"], "")}
                   for r in sorted(resultado, key=lambda r: (orden[r["accion"]], r["fila"]))],
        )
        return render(request, "cuentas/usuario_importar.html", ctx)

    request.session.pop(SESION_IMPORTAR, None)
    return render(request, "cuentas/usuario_importar.html", ctx)


@rol_requerido(ADMIN)
def usuario_importar_errores(request):
    """Excel con las filas que tienen errores, para corregirlas y volver a subirlas."""
    datos = request.session.get(SESION_IMPORTAR)
    if not datos:
        messages.error(request, "La vista previa expiró. Vuelva a subir el archivo.")
        return redirect("usuario_importar")
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Usuarios"
    titulos = [t for _, t, _, _ in importar.COLUMNAS] + ["Fila original", "Errores"]
    ws.append(titulos)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="C62828")
    rol_txt = dict(Usuario.Rol.choices)
    gen_txt = dict(Usuario.Genero.choices)
    for r in datos["resultado"]:
        if r["accion"] != "error":
            continue
        d = r["datos"]
        ws.append([d["cedula"], d["apellidos"], d["nombres"], d["correo"], d["celular"], d["direccion"], d["cargo"],
                   gen_txt.get(d["genero"], ""), rol_txt.get(d["rol"], ""), r["fila"], " ".join(r["errores"])])
    for col, ancho in zip("ABCDEFGHIJK", [14, 26, 26, 32, 13, 24, 28, 12, 20, 12, 60]):
        ws.column_dimensions[col].width = ancho
    for fila in ws.iter_rows(min_row=2, max_col=5):
        fila[0].number_format = "@"  # cédula
        fila[4].number_format = "@"  # celular
    from io import BytesIO
    buffer = BytesIO()
    wb.save(buffer)
    resp = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="usuarios_con_errores.xlsx"'
    return resp
