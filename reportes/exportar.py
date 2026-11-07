"""Generación de reportes en PDF (ReportLab) y Excel (openpyxl) con el encabezado institucional."""
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Colores institucionales (logotipo ISTAM)
AZUL = colors.HexColor("#006526")        # verde oscuro (nombre conservado)
AZUL_CLARO = colors.HexColor("#eef6e4")  # verde muy claro
LIMA = colors.HexColor("#91b423")
BORDE = colors.HexColor("#cfdcc4")
GRIS = colors.HexColor("#6b7280")
LOGO = Path(settings.BASE_DIR) / "static" / "img" / "logo_istam.png"

_estilos = getSampleStyleSheet()
E_NORMAL = ParagraphStyle("n", parent=_estilos["Normal"], fontName="Helvetica", fontSize=8.5, leading=10.5)
E_CELDA = ParagraphStyle("c", parent=E_NORMAL, fontSize=8, leading=9.8)
E_CABECERA = ParagraphStyle("h", parent=E_CELDA, fontName="Helvetica-Bold", textColor=colors.white)
E_TITULO = ParagraphStyle("t", parent=E_NORMAL, fontName="Helvetica-Bold", fontSize=13, leading=16, alignment=TA_CENTER, textColor=AZUL, spaceAfter=2)
E_INST = ParagraphStyle("i", parent=E_NORMAL, fontName="Helvetica-Bold", fontSize=11, leading=13, alignment=TA_CENTER)
E_SUB = ParagraphStyle("s", parent=E_NORMAL, alignment=TA_CENTER, textColor=GRIS)
E_SECCION = ParagraphStyle("sec", parent=E_NORMAL, fontName="Helvetica-Bold", fontSize=10, textColor=AZUL, spaceBefore=8, spaceAfter=4)


def p(texto, estilo=E_CELDA):
    from xml.sax.saxutils import escape
    return Paragraph(escape(str(texto if texto is not None else "")).replace("\n", "<br/>"), estilo)


class _CanvasNumerado(rl_canvas.Canvas):
    """Agrega 'Página X de Y' y la fecha de generación al pie de cada hoja."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            ancho, _ = self._pagesize
            self.setFont("Helvetica", 7.5)
            self.setFillColor(GRIS)
            self.drawString(1.5 * cm, 1 * cm, f"{settings.INSTITUCION_SIGLAS} · Sistema de Soporte de Equipos Informáticos · Generado: "
                            f"{timezone.localtime().strftime('%d/%m/%Y %H:%M')}")
            self.drawRightString(ancho - 1.5 * cm, 1 * cm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def encabezado(titulo, subtitulo=""):
    """Logo horizontal centrado, departamento, franja verde lima y título del documento."""
    if LOGO.exists():
        w, h = ImageReader(str(LOGO)).getSize()
        logo = Image(str(LOGO), width=6.5 * cm, height=6.5 * cm * h / w)
        logo.hAlign = "CENTER"
        partes = [logo, Spacer(1, 3)]
    else:
        partes = [p(settings.INSTITUCION_NOMBRE, E_INST)]
    partes += [
        p(settings.DEPARTAMENTO_TIC, E_SUB), Spacer(1, 3),
        Table([[""]], colWidths=["100%"], style=[("LINEBELOW", (0, 0), (-1, -1), 2, LIMA)]),
        Spacer(1, 6), p(titulo, E_TITULO),
    ]
    if subtitulo:
        partes.append(p(subtitulo, E_SUB))
    return partes + [Spacer(1, 8)]


def tabla(columnas, filas, anchos=None, ancho_total=None):
    datos = [[p(c, E_CABECERA) for c in columnas]] + [[p(v) for v in fila] for fila in filas]
    if anchos and ancho_total:
        total = sum(anchos)
        anchos = [ancho_total * a / total for a in anchos]
    t = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(datos)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), AZUL_CLARO))
    t.setStyle(TableStyle(estilo))
    return t


def tabla_resumen(resumen, ancho_total):
    """resumen: lista de (etiqueta, valor) mostrada como tarjetas en una fila."""
    if not resumen:
        return []
    celdas = [[None] * len(resumen),
              [p(e, ParagraphStyle("e", parent=E_CELDA, alignment=TA_CENTER, textColor=GRIS)) for e, _ in resumen]]
    celdas[0] = [Paragraph(f"<b>{v}</b>", ParagraphStyle("v", parent=E_NORMAL, fontSize=12, leading=14, alignment=TA_CENTER, textColor=AZUL)) for _, v in resumen]
    t = Table(celdas, colWidths=[ancho_total / len(resumen)] * len(resumen))
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 0), (-1, -1), AZUL_CLARO),
    ]))
    return [t, Spacer(1, 8)]


def respuesta_pdf(*, titulo, columnas, filas, nombre, anchos=None, filtros="", resumen=None, usuario=None, extra=None):
    buffer = BytesIO()
    pagina = landscape(A4)
    doc = SimpleDocTemplate(buffer, pagesize=pagina, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.6 * cm, title=titulo, author=settings.INSTITUCION_SIGLAS)
    ancho = pagina[0] - 3 * cm
    sub = filtros
    if usuario:
        sub = (sub + " · " if sub else "") + f"Generado por: {usuario.nombre_completo}"
    elementos = encabezado(titulo, sub)
    elementos += tabla_resumen(resumen, ancho)
    if extra:
        elementos += extra
    if filas:
        elementos.append(tabla(columnas, filas, anchos, ancho))
    else:
        elementos.append(p("No hay registros para los filtros seleccionados.", E_NORMAL))
    elementos += [Spacer(1, 6), p(f"Total de registros: {len(filas)}", E_NORMAL)]
    doc.build(elementos, canvasmaker=_CanvasNumerado)
    resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{nombre}.pdf"'
    return resp


def respuesta_excel(*, titulo, columnas, filas, nombre, filtros="", resumen=None, usuario=None):
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    n = len(columnas)
    fila = 1
    for texto, negrita, tam in ((settings.INSTITUCION_NOMBRE, True, 13), (settings.DEPARTAMENTO_TIC, False, 10),
                                (titulo, True, 12), (filtros, False, 9)):
        if not texto:
            continue
        ws.cell(row=fila, column=1, value=texto).font = Font(bold=negrita, size=tam, color="006526" if negrita else "555555")
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=max(n, 1))
        ws.cell(row=fila, column=1).alignment = Alignment(horizontal="center")
        fila += 1
    ws.cell(row=fila, column=1, value=f"Generado: {timezone.localtime().strftime('%d/%m/%Y %H:%M')}"
            + (f" por {usuario.nombre_completo}" if usuario else "")).font = Font(size=9, color="777777")
    fila += 2
    if resumen:
        for etiqueta, valor in resumen:
            ws.cell(row=fila, column=1, value=etiqueta).font = Font(bold=True)
            ws.cell(row=fila, column=2, value=valor)
            fila += 1
        fila += 1
    borde = Border(*(Side(style="thin", color="CFDCC4"),) * 4)
    for j, c in enumerate(columnas, 1):
        celda = ws.cell(row=fila, column=j, value=c)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="006526")
        celda.alignment = Alignment(vertical="center", wrap_text=True)
        celda.border = borde
    inicio = fila
    for f in filas:
        fila += 1
        for j, v in enumerate(f, 1):
            celda = ws.cell(row=fila, column=j, value=v)
            celda.alignment = Alignment(vertical="top", wrap_text=True)
            celda.border = borde
    for j in range(1, n + 1):
        largo = max([len(str(columnas[j - 1]))] + [min(len(str(f[j - 1] or "")), 60) for f in filas])
        ws.column_dimensions[get_column_letter(j)].width = max(10, min(largo + 2, 55))
    ws.freeze_panes = ws.cell(row=inicio + 1, column=1)
    if filas:
        ws.auto_filter.ref = f"A{inicio}:{get_column_letter(n)}{fila}"
    if LOGO.exists():
        from openpyxl.drawing.image import Image as XLImage
        img = XLImage(str(LOGO))
        img.height, img.width = 46, int(46 * img.width / img.height)
        ws.add_image(img, "A1")
        ws.row_dimensions[1].height = 22
        ws.row_dimensions[2].height = 22
    buffer = BytesIO()
    wb.save(buffer)
    resp = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'
    return resp
