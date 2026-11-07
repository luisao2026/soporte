from datetime import datetime, time

from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from aplicaciones.models import Aplicacion
from cuentas.decorators import reportes_requeridos
from cuentas.models import Usuario
from cuentas.utils import paginar
from equipos.models import Categoria
from soporte.models import CategoriaApp, Diagnostico, Mantenimiento, Ticket, TipoSoporte

from .exportar import respuesta_excel, respuesta_pdf

Estado = Ticket.Estado

# Agrupación de estados según el documento: registrados, pendientes, asignados, atendidos, cerrados
GRUPOS_TICKETS = {
    "registrados": ("Tickets registrados", None),
    "pendientes": ("Tickets pendientes", [Estado.PENDIENTE]),
    "asignados": ("Tickets asignados", [Estado.ASIGNADO, Estado.EN_PROCESO]),
    "atendidos": ("Tickets atendidos", [Estado.ATENDIDO]),
    "cerrados": ("Tickets cerrados", [Estado.CERRADO]),
}


def _f(dt):
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else ""


def _rango(request):
    """Lee las fechas desde/hasta del formulario y devuelve (desde, hasta, texto)."""
    def leer(nombre):
        try:
            return datetime.strptime(request.GET.get(nombre, ""), "%Y-%m-%d").date()
        except ValueError:
            return None
    desde, hasta = leer("desde"), leer("hasta")
    texto = []
    if desde:
        texto.append(f"Desde {desde:%d/%m/%Y}")
    if hasta:
        texto.append(f"hasta {hasta:%d/%m/%Y}")
    return desde, hasta, " ".join(texto)


def _filtrar_fecha(qs, campo, desde, hasta):
    tz = timezone.get_current_timezone()
    if desde:
        qs = qs.filter(**{f"{campo}__gte": timezone.make_aware(datetime.combine(desde, time.min), tz)})
    if hasta:
        qs = qs.filter(**{f"{campo}__lte": timezone.make_aware(datetime.combine(hasta, time.max), tz)})
    return qs


def _practicante_filtro(request):
    """El practicante solo ve sus propios registros; el administrador puede filtrar por practicante."""
    u = request.user
    if u.es_practicante:
        return u, None
    pk = request.GET.get("practicante")
    practicantes = Usuario.objects.filter(rol=Usuario.Rol.PRACTICANTE)
    return (practicantes.filter(pk=pk).first() if pk and pk.isdigit() else None), practicantes


def _salida(request, *, titulo, columnas, filas, nombre, plantilla, ctx, anchos=None, filtros="", resumen=None):
    formato = request.GET.get("formato")
    if formato == "pdf":
        return respuesta_pdf(titulo=titulo, columnas=columnas, filas=filas, nombre=nombre, anchos=anchos,
                             filtros=filtros, resumen=resumen, usuario=request.user)
    if formato == "excel":
        return respuesta_excel(titulo=titulo, columnas=columnas, filas=filas, nombre=nombre,
                               filtros=filtros, resumen=resumen, usuario=request.user)
    pagina, params = paginar(request, filas, 20)
    ctx.update({"titulo": titulo, "columnas": columnas, "pagina": pagina, "params": params,
                "filtros_texto": filtros, "resumen": resumen, "total": len(filas)})
    return render(request, plantilla, ctx)


@reportes_requeridos
def indice(request):
    return render(request, "reportes/indice.html")


@reportes_requeridos
def reporte_tickets(request):
    desde, hasta, texto = _rango(request)
    practicante, practicantes = _practicante_filtro(request)
    qs = Ticket.objects.select_related("equipo", "aplicacion", "solicitante", "practicante")
    qs = _filtrar_fecha(qs, "fecha", desde, hasta)
    if practicante:
        qs = qs.filter(practicante=practicante)
    ambito = request.GET.get("ambito", "")
    if ambito in Ticket.Ambito.values:
        qs = qs.filter(ambito=ambito)
    tipo = request.GET.get("tipo", "")
    if tipo:
        qs = qs.filter(tipo_soporte=tipo)
    prioridad = request.GET.get("prioridad", "")
    if prioridad:
        qs = qs.filter(prioridad=prioridad)

    resumen = []
    for clave, (etiqueta, estados) in GRUPOS_TICKETS.items():
        resumen.append((etiqueta, qs.count() if estados is None else qs.filter(estado__in=estados).count()))

    grupo = request.GET.get("grupo", "registrados")
    if grupo not in GRUPOS_TICKETS:
        grupo = "registrados"
    etiqueta, estados = GRUPOS_TICKETS[grupo]
    if estados:
        qs = qs.filter(estado__in=estados)

    columnas = ["N.º ticket", "Fecha", "Solicitante", "Equipo / aplicación", "Marca, modelo / solicitud", "Serie", "Tipo de soporte",
                "Prioridad", "Estado", "Técnico/practicante", "Resultado"]
    filas = [[t.numero, _f(t.fecha), t.solicitante.nombre_completo, t.atendido,
              t.atendido_detalle, t.numero_serie, t.get_tipo_soporte_display(), t.get_prioridad_display(),
              t.get_estado_display(), t.practicante.nombre_completo if t.practicante else "Sin asignar",
              t.get_resultado_display()] for t in qs]
    filtros = " · ".join(x for x in [etiqueta, texto, dict(Ticket.Ambito.choices).get(ambito, ""), dict(TipoSoporte.choices).get(tipo, ""),
                                     f"Prioridad {dict(Ticket.Prioridad.choices)[prioridad].lower()}" if prioridad else "",
                                     f"Practicante: {practicante}" if practicante else ""] if x)
    return _salida(request, titulo="Reporte de tickets", columnas=columnas, filas=filas, nombre="reporte_tickets",
                   plantilla="reportes/reporte.html", filtros=filtros, resumen=resumen,
                   anchos=[2.7, 2.1, 3.2, 3.6, 2.8, 2.3, 2.6, 1.7, 1.8, 3.2, 2.2],
                   ctx={"tipo_reporte": "tickets", "ambitos": Ticket.Ambito.choices, "grupos": [(k, v[0]) for k, v in GRUPOS_TICKETS.items()], "grupo": grupo,
                        "tipos": TipoSoporte.choices, "prioridades": Ticket.Prioridad.choices, "practicantes": practicantes})


@reportes_requeridos
def reporte_diagnosticos(request):
    desde, hasta, texto = _rango(request)
    practicante, practicantes = _practicante_filtro(request)
    qs = Diagnostico.objects.select_related("ticket", "ticket__equipo", "ticket__solicitante", "realizado_por").filter(
        ticket__ambito=Ticket.Ambito.EQUIPO)  # las aplicaciones tienen su propio reporte
    qs = _filtrar_fecha(qs, "fecha", desde, hasta)
    if practicante:
        qs = qs.filter(Q(realizado_por=practicante) | Q(ticket__practicante=practicante))
    resultado = request.GET.get("resultado", "")
    if resultado == "PENDIENTE":
        qs = qs.filter(ticket__resultado="")
    elif resultado:
        qs = qs.filter(ticket__resultado=resultado)
    columnas = ["N.º ticket", "Fecha", "Equipo", "Usuario", "Problema", "Diagnóstico", "Requiere", "Técnico/practicante", "Resultado"]
    filas = [[d.ticket.numero, _f(d.fecha), f"{d.ticket.equipo.codigo} - {d.ticket.equipo.nombre}",
              d.ticket.solicitante.nombre_completo, d.ticket.problema, d.descripcion, d.get_tipo_mantenimiento_display(),
              d.realizado_por.nombre_completo, d.ticket.get_resultado_display() or "En atención"] for d in qs]
    resumen = [("Diagnósticos", len(filas))] + [
        (etq, sum(1 for d in qs if d.ticket.resultado == v)) for v, etq in Ticket.Resultado.choices if v in Ticket.RESULTADOS_EQUIPO
    ] + [("En atención", sum(1 for d in qs if not d.ticket.resultado))]
    filtros = " · ".join(x for x in [texto, dict(Ticket.Resultado.choices).get(resultado, "En atención" if resultado == "PENDIENTE" else ""),
                                     f"Practicante: {practicante}" if practicante else ""] if x)
    return _salida(request, titulo="Reporte de diagnósticos", columnas=columnas, filas=filas, nombre="reporte_diagnosticos",
                   plantilla="reportes/reporte.html", filtros=filtros, resumen=resumen,
                   anchos=[2.7, 2.1, 3.4, 3, 4.5, 5, 2.6, 3, 2.3],
                   ctx={"tipo_reporte": "diagnosticos", "resultados": [c for c in Ticket.Resultado.choices if c[0] in Ticket.RESULTADOS_EQUIPO],
                        "practicantes": practicantes})


@reportes_requeridos
def reporte_mantenimientos(request):
    desde, hasta, texto = _rango(request)
    practicante, practicantes = _practicante_filtro(request)
    qs = Mantenimiento.objects.select_related("ticket", "ticket__equipo", "ticket__equipo__categoria",
                                              "ticket__equipo__responsable", "realizado_por").filter(
        tipo__in=[Mantenimiento.Tipo.PREVENTIVO, Mantenimiento.Tipo.CORRECTIVO])
    qs = _filtrar_fecha(qs, "fecha", desde, hasta)
    if practicante:
        qs = qs.filter(Q(realizado_por=practicante) | Q(ticket__practicante=practicante))
    tipo = request.GET.get("tipo", "")
    if tipo:
        qs = qs.filter(tipo=tipo)
    categoria = request.GET.get("categoria", "")
    if categoria.isdigit():
        qs = qs.filter(ticket__equipo__categoria_id=categoria)
    columnas = ["Fecha", "N.º ticket", "Código", "Equipo", "Tipo de equipo", "Responsable", "Mantenimiento",
                "Actividades realizadas", "Repuestos", "Técnico/practicante"]
    filas = [[_f(m.fecha), m.ticket.numero, m.ticket.equipo.codigo, m.ticket.equipo.nombre, m.ticket.equipo.categoria.nombre,
              m.ticket.equipo.responsable.nombre_completo, m.get_tipo_display(), m.actividades, m.repuestos,
              m.realizado_por.nombre_completo] for m in qs]
    resumen = [
        ("Mantenimientos", len(filas)),
        ("Preventivos", sum(1 for m in qs if m.tipo == Mantenimiento.Tipo.PREVENTIVO)),
        ("Correctivos", sum(1 for m in qs if m.tipo == Mantenimiento.Tipo.CORRECTIVO)),
        ("Equipos atendidos", len({m.ticket.equipo_id for m in qs})),
    ]
    cat = Categoria.objects.filter(pk=categoria).first() if categoria.isdigit() else None
    filtros = " · ".join(x for x in [texto, f"Mantenimiento {dict(Mantenimiento.Tipo.choices).get(tipo, '').lower()}" if tipo else "",
                                     f"Tipo de equipo: {cat}" if cat else "", f"Practicante: {practicante}" if practicante else ""] if x)
    return _salida(request, titulo="Reporte de equipos por mantenimiento", columnas=columnas, filas=filas,
                   nombre="reporte_mantenimientos", plantilla="reportes/reporte.html", filtros=filtros, resumen=resumen,
                   anchos=[2.1, 2.7, 1.9, 3, 2.4, 3, 2.6, 5.3, 2.8, 3],
                   ctx={"tipo_reporte": "mantenimientos", "tipos": [c for c in Mantenimiento.Tipo.choices if c[0] != Mantenimiento.Tipo.APLICACION],
                        "categorias": Categoria.objects.all(), "practicantes": practicantes})


@reportes_requeridos
def reporte_tipos(request):
    desde, hasta, texto = _rango(request)
    practicante, practicantes = _practicante_filtro(request)
    diags = _filtrar_fecha(Diagnostico.objects.all(), "fecha", desde, hasta)
    mants = _filtrar_fecha(Mantenimiento.objects.all(), "fecha", desde, hasta)
    tickets = _filtrar_fecha(Ticket.objects.all(), "fecha", desde, hasta)
    if practicante:
        diags = diags.filter(realizado_por=practicante)
        mants = mants.filter(realizado_por=practicante)
        tickets = tickets.filter(practicante=practicante)

    # Soporte a aplicaciones = tickets de aplicación con análisis registrado
    analisis = diags.filter(ticket__ambito=Ticket.Ambito.APLICACION)
    diags = diags.filter(ticket__ambito=Ticket.Ambito.EQUIPO)
    n_diag = diags.count()
    n_prev = mants.filter(tipo=Mantenimiento.Tipo.PREVENTIVO).count()
    n_corr = mants.filter(tipo=Mantenimiento.Tipo.CORRECTIVO).count()
    n_app = analisis.count()
    total = n_diag + n_prev + n_corr + n_app
    resumen = [("Diagnósticos", n_diag), ("Mantenimientos preventivos", n_prev), ("Mantenimientos correctivos", n_corr),
               ("Soportes a aplicaciones", n_app), ("Total de soportes", total)]
    solicitados = dict(tickets.values_list("tipo_soporte").annotate(n=Count("id")))
    maximo = max([n_diag, n_prev, n_corr, n_app, 1])
    barras = [("Diagnósticos", n_diag, "primary"), ("Mantenimientos preventivos", n_prev, "success"),
              ("Mantenimientos correctivos", n_corr, "warning"), ("Soportes a aplicaciones", n_app, "info")]
    barras = [(e, n, c, round(n * 100 / maximo)) for e, n, c in barras]

    # Detalle por técnico/practicante
    personas = Usuario.objects.filter(Q(diagnosticos__in=diags) | Q(mantenimientos__in=mants) | Q(diagnosticos__in=analisis)).distinct()
    columnas = ["Técnico/practicante", "Diagnósticos", "Mant. preventivos", "Mant. correctivos", "Soporte a aplicaciones", "Total"]
    filas = []
    for per in personas:
        d = diags.filter(realizado_por=per).count()
        pv = mants.filter(realizado_por=per, tipo=Mantenimiento.Tipo.PREVENTIVO).count()
        cr = mants.filter(realizado_por=per, tipo=Mantenimiento.Tipo.CORRECTIVO).count()
        ap = analisis.filter(realizado_por=per).count()
        filas.append([per.nombre_completo, d, pv, cr, ap, d + pv + cr + ap])
    filas.sort(key=lambda f: -f[5])
    if filas:
        filas.append(["TOTAL", n_diag, n_prev, n_corr, n_app, total])

    filtros = " · ".join(x for x in [texto, f"Practicante: {practicante}" if practicante else ""] if x)
    extra = None
    if request.GET.get("formato") == "pdf":
        from reportlab.lib.units import cm

        from .exportar import E_SECCION, p, tabla
        extra = [p("Tickets solicitados por tipo de soporte", E_SECCION),
                 tabla(["Tipo de soporte solicitado", "Tickets"], [[l, solicitados.get(v, 0)] for v, l in TipoSoporte.choices], [8, 3], 12 * cm),
                 p("Soportes realizados por técnico/practicante", E_SECCION)]
        return respuesta_pdf(titulo="Reporte de tipos de soporte", columnas=columnas, filas=filas, nombre="reporte_tipos_soporte",
                             anchos=[8, 3, 3, 3, 3.4, 2.6], filtros=filtros, resumen=resumen, usuario=request.user, extra=extra)
    if request.GET.get("formato") == "excel":
        filas_xls = filas + [[""] * 6, ["Tickets solicitados por tipo"] + [""] * 5] + \
            [[l, solicitados.get(v, 0)] + [""] * 4 for v, l in TipoSoporte.choices]
        return respuesta_excel(titulo="Reporte de tipos de soporte", columnas=columnas, filas=filas_xls,
                               nombre="reporte_tipos_soporte", filtros=filtros, resumen=resumen, usuario=request.user)
    return render(request, "reportes/reporte_tipos.html", {
        "titulo": "Reporte de tipos de soporte", "resumen": resumen, "barras": barras, "columnas": columnas, "filas": filas,
        "solicitados": [(l, solicitados.get(v, 0)) for v, l in TipoSoporte.choices], "filtros_texto": filtros,
        "practicantes": practicantes, "tipo_reporte": "tipos",
    })


@reportes_requeridos
def reporte_aplicaciones(request):
    """Soporte a aplicaciones: EVA/Moodle, sitio web, SIGA, correo..."""
    desde, hasta, texto = _rango(request)
    practicante, practicantes = _practicante_filtro(request)
    qs = Ticket.objects.filter(ambito=Ticket.Ambito.APLICACION).select_related("aplicacion", "solicitante", "practicante")
    qs = _filtrar_fecha(qs, "fecha", desde, hasta)
    if practicante:
        qs = qs.filter(practicante=practicante)
    app_id = request.GET.get("aplicacion", "")
    app = Aplicacion.objects.filter(pk=app_id).first() if app_id.isdigit() else None
    if app:
        qs = qs.filter(aplicacion=app)
    categoria = request.GET.get("categoria", "")
    if categoria in CategoriaApp.values:
        qs = qs.filter(categoria_app=categoria)
    resultado = request.GET.get("resultado", "")
    if resultado == "PENDIENTE":
        qs = qs.filter(resultado="")
    elif resultado in Ticket.RESULTADOS_APLICACION:
        qs = qs.filter(resultado=resultado)

    tickets = list(qs)
    columnas = ["N.º ticket", "Fecha", "Aplicación", "Tipo de solicitud", "Solicitante", "Afecta a", "Detalle",
                "Técnico/practicante", "Estado", "Resultado"]
    filas = [[t.numero, _f(t.fecha), t.aplicacion.nombre, t.get_categoria_app_display(), t.solicitante.nombre_completo,
              t.referencia, t.problema, t.practicante.nombre_completo if t.practicante else "Sin asignar",
              t.get_estado_display(), t.get_resultado_display() or "En atención"] for t in tickets]
    resumen = [("Solicitudes", len(tickets))] + [
        (etq, sum(1 for t in tickets if t.resultado == v)) for v, etq in Ticket.Resultado.choices if v in Ticket.RESULTADOS_APLICACION
    ] + [("En atención", sum(1 for t in tickets if not t.resultado))]
    filtros = " · ".join(x for x in [
        texto, f"Aplicación: {app}" if app else "", dict(CategoriaApp.choices).get(categoria, ""),
        dict(Ticket.Resultado.choices).get(resultado, "En atención" if resultado == "PENDIENTE" else ""),
        f"Practicante: {practicante}" if practicante else ""] if x)
    return _salida(request, titulo="Reporte de soporte a aplicaciones", columnas=columnas, filas=filas,
                   nombre="reporte_aplicaciones", plantilla="reportes/reporte.html", filtros=filtros, resumen=resumen,
                   anchos=[2.6, 2.1, 3.2, 3, 3, 3, 5, 3, 1.8, 2.4],
                   ctx={"tipo_reporte": "aplicaciones", "aplicaciones": Aplicacion.objects.all(), "categorias_app": CategoriaApp.choices,
                        "resultados": [c for c in Ticket.Resultado.choices if c[0] in Ticket.RESULTADOS_APLICACION],
                        "practicantes": practicantes})
