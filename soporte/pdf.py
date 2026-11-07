"""Informe de soporte técnico (orden de servicio) de un ticket, en PDF."""
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Spacer, Table, TableStyle

from reportes.exportar import AZUL_CLARO, BORDE, E_CELDA, E_NORMAL, E_SECCION, _CanvasNumerado, encabezado, p, tabla


def _f(dt):
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else "—"


def _ficha(pares, ancho):
    """Tabla de dos columnas etiqueta/valor repetida en 2 bloques por fila."""
    filas = []
    for i in range(0, len(pares), 2):
        fila = []
        for etq, val in pares[i:i + 2]:
            fila += [p(f"{etq}:", E_CELDA), p(val)]
        while len(fila) < 4:
            fila += ["", ""]
        filas.append(fila)
    t = Table(filas, colWidths=[ancho * 0.19, ancho * 0.31, ancho * 0.19, ancho * 0.31])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 0), (0, -1), AZUL_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), AZUL_CLARO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def pdf_ticket(t):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.2 * cm,
                            bottomMargin=1.6 * cm, title=f"Ticket {t.numero}")
    ancho = A4[0] - 3.6 * cm
    e = t.equipo
    app = t.es_aplicacion
    el = encabezado("INFORME DE SOPORTE TÉCNICO", f"Ticket {t.numero} · Estado: {t.get_estado_display()}")

    el += [p("1. Datos del ticket", E_SECCION), _ficha([
        ("N.º ticket", t.numero), ("Fecha", _f(t.fecha)),
        ("Solicitante", t.solicitante.nombre_completo), ("Cédula", t.solicitante.cedula or "—"),
        ("Cargo / rol", t.solicitante.cargo or t.solicitante.get_rol_display()), ("Tipo de soporte", t.get_tipo_soporte_display()),
        ("Prioridad", t.get_prioridad_display()), ("Estado", t.get_estado_display()),
    ], ancho), Spacer(1, 4), p(f"{'Detalle de la solicitud' if app else 'Problema reportado'}: {t.problema}", E_NORMAL)]

    if app:
        a = t.aplicacion
        el += [p("2. Datos de la aplicación", E_SECCION), _ficha([
            ("Aplicación", a.nombre), ("Plataforma", a.plataforma or a.get_tipo_display()),
            ("Tipo de solicitud", t.get_categoria_app_display()), ("Dirección", a.url or "—"),
            ("Afecta a", t.referencia or "—"), ("Responsable técnico", a.responsable.nombre_completo if a.responsable else "—"),
        ], ancho)]
    else:
        el += [p("2. Datos del equipo", E_SECCION), _ficha([
        ("Código", e.codigo), ("Nombre", e.nombre),
        ("Tipo de equipo", e.categoria.nombre), ("Marca", t.marca),
        ("Modelo", t.modelo), ("N.º de serie", t.numero_serie),
        ("Responsable", e.responsable.nombre_completo), ("Estado actual", e.get_estado_display()),
        ], ancho)]

    el += [p("3. Asignación", E_SECCION), _ficha([
        ("Técnico/practicante", t.practicante.nombre_completo if t.practicante else "Sin asignar"),
        ("Fecha de asignación", _f(t.fecha_asignacion)),
    ], ancho)]

    diag = t.diagnostico_o_none()
    el.append(p("4. Análisis del problema" if app else "4. Diagnóstico", E_SECCION))
    if diag and app:
        el.append(_ficha([
            ("Fecha", _f(diag.fecha)), ("Realizado por", diag.realizado_por.nombre_completo),
            ("Análisis", diag.descripcion), ("Causa identificada", diag.causa or "—"),
            ("Recomendaciones", diag.recomendacion or "—"),
        ], ancho))
    elif diag:
        el.append(_ficha([
            ("Fecha", _f(diag.fecha)), ("Realizado por", diag.realizado_por.nombre_completo),
            ("Diagnóstico", diag.descripcion), ("Causa probable", diag.causa or "—"),
            ("Requiere", diag.get_tipo_mantenimiento_display()), ("Recomendaciones", diag.recomendacion or "—"),
        ], ancho))
    else:
        el.append(p("Sin análisis registrado." if app else "Sin diagnóstico registrado.", E_NORMAL))

    el.append(p("5. Acciones realizadas" if app else "5. Mantenimientos realizados", E_SECCION))
    mants = list(t.mantenimientos.select_related("realizado_por").order_by("fecha"))
    if mants and app:
        el.append(tabla(["Fecha", "Acciones realizadas", "Herramientas / referencias", "Realizado por"],
                        [[_f(m.fecha), m.actividades, m.repuestos or "—", m.realizado_por.nombre_completo] for m in mants],
                        [2.6, 8, 3.8, 3.2], ancho))
    elif mants:
        el.append(tabla(["Fecha", "Tipo", "Actividades realizadas", "Repuestos / materiales", "Realizado por"],
                        [[_f(m.fecha), m.get_tipo_display(), m.actividades, m.repuestos or "—", m.realizado_por.nombre_completo] for m in mants],
                        [2.6, 2.2, 6, 3.6, 3.2], ancho))
    else:
        el.append(p("Sin acciones registradas." if app else "Sin mantenimientos registrados.", E_NORMAL))

    obs = list(t.observaciones.select_related("autor"))
    if obs:
        el.append(p("6. Observaciones", E_SECCION))
        el.append(tabla(["Fecha", "Autor", "Observación"], [[_f(o.fecha), o.autor.nombre_completo, o.texto] for o in obs], [2.6, 4, 11], ancho))

    el += [p("7. Resultado y cierre", E_SECCION), _ficha([
        ("Resultado", t.get_resultado_display() or "En atención"), ("Fecha de atención", _f(t.fecha_atencion)),
        ("Detalle", t.detalle_resultado or "—"), ("Fecha de cierre", _f(t.fecha_cierre)),
    ], ancho)]

    firmas = Table([
        ["", "", ""],
        [p("Técnico/practicante\n" + (t.practicante.nombre_completo if t.practicante else ""), E_CELDA),
         p("Usuario solicitante\n" + t.solicitante.nombre_completo, E_CELDA),
         p("Responsable de TIC", E_CELDA)],
    ], colWidths=[ancho / 3] * 3, rowHeights=[1.8 * cm, None])
    firmas.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), 0.6, colors.black), ("LINEABOVE", (1, 1), (1, 1), 0.6, colors.black),
        ("LINEABOVE", (2, 1), (2, 1), 0.6, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    el += [Spacer(1, 18), KeepTogether([p(f"{settings.INSTITUCION_CIUDAD}, {timezone.localtime():%d/%m/%Y}", E_NORMAL), firmas])]

    doc.build(el, canvasmaker=_CanvasNumerado)
    resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{t.numero}.pdf"'
    return resp
