"""
Carga masiva de usuarios desde Excel (.xlsx) o CSV.

Flujo: leer archivo → normalizar y validar cada fila (vista previa) → confirmar → crear / actualizar.
El usuario y la contraseña inicial de cada usuario nuevo son su cédula.
"""
import csv
import io
import re
import unicodedata
from io import BytesIO

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .models import Usuario
from .validators import cedula_valida

# Columnas de la plantilla: (clave, título, obligatoria, ancho)
COLUMNAS = [
    ("cedula", "Cédula", True, 14),
    ("apellidos", "Apellidos", True, 26),
    ("nombres", "Nombres", True, 26),
    ("correo", "Correo", True, 32),
    ("celular", "Celular", False, 13),
    ("direccion", "Dirección", False, 28),
    ("cargo", "Cargo", False, 32),
    ("genero", "Género", False, 12),
    ("rol", "Rol", True, 20),
]

# Nombres alternativos que se aceptan en el encabezado del archivo
ALIAS = {
    "cedula": ["cedula", "ci", "identificacion", "cedula de identidad", "documento", "numero de cedula"],
    "apellidos": ["apellidos", "apellido"],
    "nombres": ["nombres", "nombre"],
    "correo": ["correo", "email", "e-mail", "correo electronico", "correo institucional", "mail"],
    "celular": ["celular", "telefono", "movil", "telefono celular", "numero de celular"],
    "direccion": ["direccion", "domicilio"],
    "cargo": ["cargo", "carrera", "puesto", "funcion"],
    "genero": ["genero", "sexo"],
    "rol": ["rol", "tipo", "tipo de usuario", "perfil"],
}

GENEROS = {"m": "M", "masculino": "M", "hombre": "M", "f": "F", "femenino": "F", "mujer": "F", "o": "O", "otro": "O"}


def sin_tildes(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()


def _clave_encabezado(titulo):
    t = re.sub(r"[*:()\[\]]", " ", sin_tildes(titulo))
    t = re.sub(r"\s+", " ", t).strip()
    for clave, alias in ALIAS.items():
        if t in alias:
            return clave
    return None


ROLES = {}
for valor, etiqueta in Usuario.Rol.choices:
    ROLES[sin_tildes(valor)] = valor
    ROLES[sin_tildes(etiqueta)] = valor
ROLES.update({"responsable tic": "TIC", "tic": "TIC", "admin": "ADMIN", "docentes": "DOCENTE", "estudiantes": "ESTUDIANTE",
              "practicantes": "PRACTICANTE", "alumno": "ESTUDIANTE", "profesor": "DOCENTE"})


def _texto(valor):
    """Convierte la celda a texto. Excel guarda las cédulas como número (1104680135.0)."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _solo_digitos(valor, largo):
    """Recupera el cero inicial que Excel quita a cédulas y celulares (104680135 -> 0104680135)."""
    v = re.sub(r"[\s\-.]", "", _texto(valor))
    if v.isdigit() and len(v) == largo - 1:
        v = "0" + v
    return v


class ArchivoInvalido(Exception):
    pass


def leer_archivo(archivo):
    """Devuelve una lista de diccionarios {clave: valor} con las filas no vacías del archivo."""
    nombre = (archivo.name or "").lower()
    if nombre.endswith(".xlsx"):
        try:
            wb = load_workbook(archivo, read_only=True, data_only=True)
        except Exception:
            raise ArchivoInvalido("No se pudo abrir el archivo de Excel. Verifique que sea un .xlsx válido.")
        ws = wb["Usuarios"] if "Usuarios" in wb.sheetnames else wb.worksheets[0]
        filas = list(ws.iter_rows(values_only=True))
    elif nombre.endswith(".csv"):
        crudo = archivo.read()
        for codificacion in ("utf-8-sig", "latin-1"):
            try:
                texto = crudo.decode(codificacion)
                break
            except UnicodeDecodeError:
                continue
        separador = ";" if texto.count(";") > texto.count(",") else ","
        filas = list(csv.reader(io.StringIO(texto), delimiter=separador))
    else:
        raise ArchivoInvalido("Formato no admitido. Suba un archivo de Excel (.xlsx) o CSV.")

    # Busca la fila de encabezados (la primera que tenga la columna Cédula)
    inicio, mapa = None, {}
    for i, fila in enumerate(filas[:15]):
        candidato = {}
        for j, celda in enumerate(fila or []):
            clave = _clave_encabezado(celda)
            if clave and clave not in candidato:
                candidato[clave] = j
        if "cedula" in candidato:
            inicio, mapa = i, candidato
            break
    if inicio is None:
        raise ArchivoInvalido("No se encontró la fila de encabezados. La primera fila debe tener las columnas Cédula, Apellidos, Nombres, Correo...")
    faltan = [titulo for clave, titulo, obligatoria, _ in COLUMNAS if obligatoria and clave not in mapa and clave != "rol"]
    if faltan:
        raise ArchivoInvalido(f"Faltan columnas obligatorias en el archivo: {', '.join(faltan)}.")

    resultado = []
    for n, fila in enumerate(filas[inicio + 1:], start=inicio + 2):
        fila = list(fila or [])
        datos = {clave: (fila[j] if j < len(fila) else None) for clave, j in mapa.items()}
        if all(_texto(v) == "" for v in datos.values()):
            continue
        datos["_fila"] = n
        resultado.append(datos)
    if not resultado:
        raise ArchivoInvalido("El archivo no tiene usuarios (solo encabezados).")
    if len(resultado) > settings.IMPORTAR_MAX_FILAS:
        raise ArchivoInvalido(f"El archivo tiene {len(resultado)} filas; el máximo por carga es {settings.IMPORTAR_MAX_FILAS}. Divídalo en varios archivos.")
    return resultado


def validar(filas, *, rol_defecto="", actualizar=False):
    """
    Normaliza y valida cada fila. Devuelve una lista de diccionarios con:
    fila, datos normalizados, accion ('crear' | 'actualizar' | 'omitir' | 'error') y lista de errores/avisos.
    """
    cedulas = [_solo_digitos(f.get("cedula"), 10) for f in filas]
    correos = [_texto(f.get("correo")).lower() for f in filas]
    existentes = {u.cedula: u for u in Usuario.objects.filter(cedula__in=[c for c in cedulas if c])}
    por_usuario = {u.username: u for u in Usuario.objects.filter(username__in=[c for c in cedulas if c])}
    correos_bd = dict(Usuario.objects.filter(email__in=[c for c in correos if c]).values_list("email", "cedula"))
    vistas_ced, vistas_correo = {}, {}
    salida = []

    for f in filas:
        errores, avisos = [], []
        cedula = _solo_digitos(f.get("cedula"), 10)
        d = {
            "cedula": cedula,
            "apellidos": re.sub(r"\s+", " ", _texto(f.get("apellidos"))).upper(),
            "nombres": re.sub(r"\s+", " ", _texto(f.get("nombres"))).upper(),
            "correo": _texto(f.get("correo")).lower(),
            "celular": _solo_digitos(f.get("celular"), 10),
            "direccion": _texto(f.get("direccion"))[:200],
            "cargo": _texto(f.get("cargo"))[:100],
            "genero": "",
            "rol": "",
        }
        # Cédula
        if not cedula:
            errores.append("Falta la cédula.")
        elif not cedula_valida(cedula):
            errores.append(f"Cédula no válida ({cedula}).")
        elif cedula in vistas_ced:
            errores.append(f"Cédula repetida en el archivo (fila {vistas_ced[cedula]}).")
        else:
            vistas_ced[cedula] = f["_fila"]
        # Nombres
        if not d["apellidos"]:
            errores.append("Faltan los apellidos.")
        if not d["nombres"]:
            errores.append("Faltan los nombres.")
        # Correo
        if not d["correo"]:
            errores.append("Falta el correo.")
        else:
            try:
                validate_email(d["correo"])
            except ValidationError:
                errores.append(f"Correo no válido ({d['correo']}).")
            else:
                if d["correo"] in vistas_correo:
                    errores.append(f"Correo repetido en el archivo (fila {vistas_correo[d['correo']]}).")
                else:
                    vistas_correo[d["correo"]] = f["_fila"]
                if d["correo"] in correos_bd and correos_bd[d["correo"]] != cedula:
                    errores.append("El correo ya pertenece a otro usuario del sistema.")
        # Celular
        if d["celular"] and (not d["celular"].isdigit() or len(d["celular"]) != 10 or not d["celular"].startswith("09")):
            avisos.append(f"Celular no válido ({d['celular']}); se dejará vacío.")
            d["celular"] = ""
        # Género
        g = sin_tildes(f.get("genero"))
        if g:
            if g in GENEROS:
                d["genero"] = GENEROS[g]
            else:
                avisos.append(f"Género no reconocido ({_texto(f.get('genero'))}); se dejará vacío.")
        # Rol
        r = sin_tildes(f.get("rol"))
        if r:
            d["rol"] = ROLES.get(r, "")
            if not d["rol"]:
                errores.append(f"Rol no reconocido ({_texto(f.get('rol'))}). Use: Docente, Estudiante, Practicante, Responsable de TIC o Administrador.")
        elif rol_defecto:
            d["rol"] = rol_defecto
        else:
            errores.append("Falta el rol.")

        # ¿Nuevo o ya existe?
        existente = existentes.get(cedula) or por_usuario.get(cedula)
        if errores:
            accion = "error"
        elif existente:
            if actualizar:
                accion = "actualizar"
                if existente.is_superuser and d["rol"] != Usuario.Rol.ADMIN:
                    accion = "omitir"
                    avisos.append("Es un superusuario; no se modifica desde la carga masiva.")
            else:
                accion = "omitir"
                avisos.append("Ya existe un usuario con esta cédula.")
        else:
            accion = "crear"
        salida.append({"fila": f["_fila"], "datos": d, "accion": accion, "errores": errores, "avisos": avisos,
                       "existente_id": existente.pk if existente else None})
    return salida


def resumen(resultado):
    total = {"crear": 0, "actualizar": 0, "omitir": 0, "error": 0}
    for r in resultado:
        total[r["accion"]] += 1
    return total


@transaction.atomic
def aplicar(resultado):
    """Crea o actualiza los usuarios válidos. Devuelve (creados, actualizados)."""
    creados = actualizados = 0
    nuevos = []
    for r in resultado:
        d = r["datos"]
        campos = dict(first_name=d["nombres"], last_name=d["apellidos"], email=d["correo"], rol=d["rol"],
                      is_staff=d["rol"] == Usuario.Rol.ADMIN)
        opcionales = {k: d[k] for k in ("celular", "direccion", "cargo", "genero") if d[k]}
        if r["accion"] == "crear":
            # Doble control por si alguien lo registró entre la vista previa y la confirmación
            if Usuario.objects.filter(cedula=d["cedula"]).exists() or Usuario.objects.filter(username=d["cedula"]).exists():
                continue
            nuevos.append(Usuario(username=d["cedula"], cedula=d["cedula"], is_active=True,
                                  password=make_password(d["cedula"], hasher="pbkdf2_sha256_importacion"),
                                  **campos, **opcionales))
        elif r["accion"] == "actualizar":
            u = Usuario.objects.filter(pk=r["existente_id"]).first()
            if not u:
                continue
            for k, v in {**campos, **opcionales}.items():
                setattr(u, k, v)
            if not u.cedula:
                u.cedula = d["cedula"]
            u.save()
            actualizados += 1
    if nuevos:
        Usuario.objects.bulk_create(nuevos, batch_size=500)
        creados = len(nuevos)
    return creados, actualizados


def plantilla_excel():
    """Plantilla de Excel con encabezados, listas desplegables e instrucciones."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Usuarios"
    verde = PatternFill("solid", fgColor="006526")
    for j, (_, titulo, obligatoria, ancho) in enumerate(COLUMNAS, start=1):
        c = ws.cell(row=1, column=j, value=titulo + (" *" if obligatoria else ""))
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = verde
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[c.column_letter].width = ancho
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"
    # Cédula y celular como texto para que Excel no borre el cero inicial
    for fila in range(2, 3002):
        ws.cell(row=fila, column=1).number_format = "@"
        ws.cell(row=fila, column=5).number_format = "@"
    roles = DataValidation(type="list", formula1='"Docente,Estudiante,Practicante,Responsable de TIC,Administrador"', allow_blank=True)
    roles.error = "Seleccione un rol de la lista."
    generos = DataValidation(type="list", formula1='"Masculino,Femenino,Otro"', allow_blank=True)
    ws.add_data_validation(roles)
    ws.add_data_validation(generos)
    roles.add("I2:I3001")
    generos.add("H2:H3001")

    ins = wb.create_sheet("Instrucciones")
    ins.column_dimensions["A"].width = 22
    ins.column_dimensions["B"].width = 90
    lineas = [
        ("CARGA MASIVA DE USUARIOS", ""),
        ("", ""),
        ("Cómo llenar", "Escriba un usuario por fila en la hoja «Usuarios», desde la fila 2. No cambie los encabezados."),
        ("", "Las columnas con * son obligatorias. El rol puede omitirse si elige un «rol por defecto» al subir el archivo."),
        ("", "El usuario y la contraseña inicial de cada persona serán su número de cédula."),
        ("", ""),
        ("Cédula *", "10 dígitos, con el cero inicial (ej.: 0102345678). La columna ya está con formato de texto."),
        ("Apellidos *", "Ej.: PÉREZ LOJA. Se guardan en mayúsculas."),
        ("Nombres *", "Ej.: ANA MARÍA. Se guardan en mayúsculas."),
        ("Correo *", "Correo institucional, no debe repetirse. Ej.: ana.perez@istam.edu.ec"),
        ("Celular", "10 dígitos empezando por 09. Opcional."),
        ("Dirección", "Opcional."),
        ("Cargo", "Ej.: Docente de Contabilidad / Estudiante de Desarrollo de Software. Opcional."),
        ("Género", "Masculino, Femenino u Otro (también M / F / O). Opcional."),
        ("Rol *", "Docente, Estudiante, Practicante, Responsable de TIC o Administrador."),
        ("", ""),
        ("Ejemplo", "1104680135 | PÉREZ LOJA | ANA MARÍA | ana.perez@istam.edu.ec | 0991234567 | Yantzaza | Docente de Contabilidad | Femenino | Docente"),
        ("", ""),
        ("También puede", "Subir un archivo .csv o un Excel propio: el sistema reconoce encabezados como «Cédula», «CI», «Email», «Teléfono», «Sexo»."),
        ("", "Antes de guardar, el sistema le muestra una vista previa con los errores de cada fila."),
    ]
    for i, (a, b) in enumerate(lineas, start=1):
        ins.cell(row=i, column=1, value=a).font = Font(bold=True, color="006526", size=13 if i == 1 else 11)
        ins.cell(row=i, column=2, value=b).alignment = Alignment(wrap_text=True, vertical="top")
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
