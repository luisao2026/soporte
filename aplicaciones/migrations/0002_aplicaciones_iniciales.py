from django.db import migrations

APLICACIONES = [
    # nombre, plataforma, tipo, descripción
    ("EVA - Entorno Virtual de Aprendizaje", "Moodle", "EDUCATIVA",
     "Aulas virtuales, cursos, tareas y calificaciones de docentes y estudiantes."),
    ("Sitio web institucional", "WordPress", "WEB",
     "Página web pública del instituto: noticias, publicaciones y transparencia."),
    ("SIGA - Sistema de Gestión Académica", "SIGA", "ACADEMICO",
     "Matrículas, notas, asistencia y récord académico."),
    ("Correo institucional", "Google Workspace / Microsoft 365", "CORREO",
     "Cuentas de correo institucional de docentes, estudiantes y personal."),
]


def cargar(apps, schema_editor):
    Aplicacion = apps.get_model("aplicaciones", "Aplicacion")
    for nombre, plataforma, tipo, descripcion in APLICACIONES:
        Aplicacion.objects.get_or_create(nombre=nombre, defaults={
            "plataforma": plataforma, "tipo": tipo, "descripcion": descripcion})


class Migration(migrations.Migration):
    dependencies = [("aplicaciones", "0001_initial")]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
