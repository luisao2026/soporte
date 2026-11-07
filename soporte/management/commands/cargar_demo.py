"""Carga usuarios, equipos y tickets de prueba.  Uso:  python manage.py cargar_demo"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from aplicaciones.models import Aplicacion
from cuentas.models import Usuario
from equipos.models import Categoria, Equipo, Marca, Modelo
from soporte import servicios
from soporte.models import Historial, Mantenimiento, Ticket

CLAVE = "istam2026"
R = Usuario.Rol


def cedula(base):
    """Genera una cédula ecuatoriana válida (provincia 19 = Zamora Chinchipe) a partir de 8 dígitos."""
    nueve = f"19{base:07d}"[:9]
    suma = 0
    for i, d in enumerate(nueve):
        n = int(d) * (2 if i % 2 == 0 else 1)
        suma += n - 9 if n > 9 else n
    return nueve + str((10 - suma % 10) % 10)


USUARIOS = [
    # usuario, rol, nombres, apellidos, cargo, género
    ("admin", R.ADMIN, "Carlos Andrés", "Jiménez Torres", "Administrador del sistema", "M"),
    ("tic", R.TIC, "María Fernanda", "Cueva Ortega", "Responsable del Departamento de TIC", "F"),
    ("practicante1", R.PRACTICANTE, "Kevin Josué", "Armijos Pardo", "Practicante de Desarrollo de Software", "M"),
    ("practicante2", R.PRACTICANTE, "Andrea Lucía", "Sarango Ochoa", "Practicante de Desarrollo de Software", "F"),
    ("docente1", R.DOCENTE, "Luis Alberto", "Pineda Castillo", "Docente de Contabilidad", "M"),
    ("docente2", R.DOCENTE, "Diana Carolina", "Mora Jaramillo", "Docente de Enfermería", "F"),
    ("estudiante1", R.ESTUDIANTE, "Jhon Patricio", "Tene Chalán", "Estudiante de Desarrollo de Software", "M"),
    ("estudiante2", R.ESTUDIANTE, "Gabriela Estefanía", "Loján Maza", "Estudiante de Administración", "F"),
]

EQUIPOS = [
    # responsable, nombre, categoría, marca, modelo, serie, especificaciones
    ("docente1", "Laptop de docencia", "Laptop", "HP", "ProBook 450 G8", "5CD1234ABC", "Intel Core i5 11.ª gen, 8 GB RAM, SSD 256 GB, Windows 11"),
    ("docente1", "Proyector del aula 4", "Proyector", "Acer", "Veriton X", "PJ-ACR-7781", "Proyector 3500 lúmenes, HDMI/VGA"),
    ("docente2", "Computador de laboratorio de enfermería", "Computadora de escritorio", "Dell", "OptiPlex 7090", "DL7090-55TQ", "Intel Core i7, 16 GB RAM, HDD 1 TB"),
    ("docente2", "Tablet de prácticas", "Tablet", "Lenovo", "Tab M10", "HA1B2C3D", "Android 12, 64 GB"),
    ("estudiante1", "Laptop personal", "Computadora portátil", "Lenovo", "IdeaPad 3", "PF3XK9LM", "AMD Ryzen 5, 8 GB RAM, SSD 512 GB"),
    ("estudiante1", "Celular", "Dispositivo móvil", "Asus", "Zenfone 9", "ASUS-MV-00912", "Android 13, 128 GB"),
    ("estudiante2", "Laptop de estudio", "Laptop", "Asus", "VivoBook 15", "M2N0CV12A", "Intel Core i3, 4 GB RAM, HDD 500 GB"),
    ("tic", "Computador de secretaría", "Computadora de escritorio", "HP", "EliteDesk 800 G6", "MXL0457Q2B", "Intel Core i5, 8 GB RAM, Windows 10"),
    ("tic", "Computador de biblioteca", "Computadora de escritorio", "Lenovo", "ThinkCentre M70q", "MJ0F4T7Z", "Intel Core i3, 8 GB RAM"),
    ("docente1", "Laptop de coordinación", "Laptop", "Dell", "Latitude 5420", "7HQ8R53", "Intel Core i5, 16 GB RAM, SSD 512 GB"),
]


class Command(BaseCommand):
    help = "Carga datos de demostración (usuarios, equipos y tickets en diferentes estados)."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true", help="Borra tickets, equipos y usuarios de prueba y los vuelve a crear.")

    def handle(self, *args, **opciones):
        # Durante la carga no se envían (ni imprimen) los correos de aviso
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"), transaction.atomic():
            self._cargar(opciones)

    def _cargar(self, opciones):
        if Usuario.objects.filter(username="admin").exists() and not opciones["forzar"]:
            self.stdout.write(self.style.WARNING("Los datos de prueba ya existen. Use --forzar para recrearlos."))
            return
        if opciones["forzar"]:
            Ticket.objects.all().delete()
            Equipo.objects.all().delete()
            Usuario.objects.filter(username__in=[u[0] for u in USUARIOS]).delete()

        u = {}
        for i, (usuario, rol, nombres, apellidos, cargo, genero) in enumerate(USUARIOS, start=1):
            obj = Usuario(
                username=usuario, rol=rol, first_name=nombres.upper(), last_name=apellidos.upper(),
                email=f"{usuario}@istam.edu.ec", cedula=cedula(1234500 + i * 37), celular=f"09{87654300 + i}",
                direccion="Yantzaza, Zamora Chinchipe", cargo=cargo, genero=genero,
                is_staff=rol == R.ADMIN, is_superuser=rol == R.ADMIN,
            )
            obj.set_password(CLAVE)
            obj.save()
            u[usuario] = obj

        e = []
        ahora = timezone.now()
        for i, (resp, nombre, cat, marca, modelo, serie, espec) in enumerate(EQUIPOS):
            m = Marca.objects.get(nombre=marca)
            e.append(Equipo.objects.create(
                nombre=nombre, categoria=Categoria.objects.get(nombre=cat), marca=m,
                modelo=Modelo.objects.get_or_create(marca=m, nombre=modelo)[0], numero_serie=serie,
                especificaciones=espec, responsable=u[resp], registrado_por=u[resp],
                fecha_registro=ahora - timedelta(days=60 - i),
            ))

        admin, p1, p2 = u["admin"], u["practicante1"], u["practicante2"]

        def ticket(equipo, solicitante, problema, tipo, prioridad, dias):
            t = servicios.crear_ticket(equipo=equipo, solicitante=solicitante, creado_por=solicitante,
                                       problema=problema, tipo_soporte=tipo, prioridad=prioridad)
            Ticket.objects.filter(pk=t.pk).update(fecha=ahora - timedelta(days=dias))
            t.refresh_from_db()
            return t

        # 1. Cerrado - correctivo reparado
        t = ticket(e[0], u["docente1"], "La laptop se apaga sola a los 10 minutos de uso y se calienta mucho.", "DIAGNOSTICO", "ALTA", 40)
        servicios.asignar(t, practicante=p1, tipo_soporte="CORRECTIVO", prioridad="ALTA", por=admin)
        servicios.guardar_diagnostico(t, por=p1, datos=dict(
            descripcion="Ventilador obstruido por polvo y pasta térmica seca; el procesador llega a 98 °C.",
            causa="Falta de mantenimiento por más de dos años.", tipo_mantenimiento="CORRECTIVO",
            recomendacion="Realizar mantenimiento preventivo cada 6 meses."))
        servicios.registrar_mantenimiento(t, por=p1, datos=dict(
            tipo="CORRECTIVO", actividades="Desarmado, limpieza del ventilador y disipador, cambio de pasta térmica, prueba de estrés de 30 minutos.",
            repuestos="Pasta térmica Arctic MX-4"))
        servicios.registrar_resultado(t, resultado="REPARADO", detalle="El equipo funciona normalmente; temperatura máxima 72 °C.", por=p1)
        servicios.cerrar(t, por=u["tic"], comentario="Equipo entregado al docente.")

        # 2. Cerrado - preventivo
        t = ticket(e[2], u["docente2"], "Solicito mantenimiento preventivo del computador del laboratorio antes del inicio de clases.", "PREVENTIVO", "MEDIA", 30)
        servicios.asignar(t, practicante=p2, tipo_soporte="PREVENTIVO", prioridad="MEDIA", por=admin)
        servicios.guardar_diagnostico(t, por=p2, datos=dict(
            descripcion="Equipo operativo, con acumulación de polvo y 40 actualizaciones pendientes.", causa="",
            tipo_mantenimiento="PREVENTIVO", recomendacion="Reemplazar el disco duro por SSD para mejorar el rendimiento."))
        servicios.registrar_mantenimiento(t, por=p2, datos=dict(
            tipo="PREVENTIVO", actividades="Limpieza interna y externa, actualización de Windows y antivirus, desfragmentación y limpieza de temporales.", repuestos=""))
        servicios.registrar_resultado(t, resultado="REPARADO", detalle="Mantenimiento preventivo completado.", por=p2)
        servicios.cerrar(t, por=admin)

        # 3. Cerrado - no reparado
        t = ticket(e[6], u["estudiante2"], "La pantalla de la laptop está rota después de una caída.", "CORRECTIVO", "MEDIA", 25)
        servicios.asignar(t, practicante=p1, tipo_soporte="CORRECTIVO", prioridad="MEDIA", por=admin)
        servicios.guardar_diagnostico(t, por=p1, datos=dict(
            descripcion="Panel LCD de 15.6\" fracturado; el resto del equipo funciona con monitor externo.",
            causa="Golpe físico.", tipo_mantenimiento="CORRECTIVO", recomendacion="Adquirir un panel de reemplazo compatible."))
        servicios.registrar_resultado(t, resultado="NO_REPARADO", detalle="El departamento no dispone del repuesto. Se entrega el equipo con el informe técnico.", por=p1)
        servicios.cerrar(t, por=admin)

        # 4. Atendido (por cerrar) - devolución
        t = ticket(e[4], u["estudiante1"], "La laptop está muy lenta y aparecen ventanas de publicidad.", "DIAGNOSTICO", "BAJA", 12)
        servicios.asignar(t, practicante=p2, tipo_soporte="CORRECTIVO", prioridad="BAJA", por=admin)
        servicios.guardar_diagnostico(t, por=p2, datos=dict(
            descripcion="Software publicitario instalado en el navegador y 3 programas de inicio innecesarios.",
            causa="Instalación de programas de fuentes no confiables.", tipo_mantenimiento="CORRECTIVO", recomendacion=""))
        servicios.registrar_mantenimiento(t, por=p2, datos=dict(
            tipo="CORRECTIVO", actividades="Eliminación de adware, restablecimiento del navegador y depuración del inicio.", repuestos=""))
        servicios.registrar_resultado(t, resultado="DEVOLUCION", detalle="Se devuelve el equipo al estudiante con recomendaciones de uso.", por=p2)

        # 5. En proceso (con diagnóstico)
        t = ticket(e[7], u["tic"], "El computador no reconoce la impresora de secretaría.", "DIAGNOSTICO", "URGENTE", 4)
        servicios.asignar(t, practicante=p1, tipo_soporte="DIAGNOSTICO", prioridad="URGENTE", por=admin)
        servicios.guardar_diagnostico(t, por=p1, datos=dict(
            descripcion="Controlador de impresora dañado tras actualización de Windows.", causa="Actualización automática.",
            tipo_mantenimiento="CORRECTIVO", recomendacion=""))

        # 6. Asignado
        t = ticket(e[1], u["docente1"], "El proyector muestra los colores con tono amarillento.", "CORRECTIVO", "MEDIA", 2)
        servicios.asignar(t, practicante=p2, tipo_soporte="CORRECTIVO", prioridad="MEDIA", por=admin)

        # 7 y 8. Pendientes de asignar
        ticket(e[3], u["docente2"], "La tablet no carga la batería.", "DIAGNOSTICO", "ALTA", 1)
        ticket(e[9], u["docente1"], "Mantenimiento preventivo de la laptop de coordinación.", "PREVENTIVO", "BAJA", 0)

        # ---- Soporte a aplicaciones (EVA/Moodle, sitio web, SIGA, correo) ----
        eva = Aplicacion.objects.filter(nombre__icontains="EVA").first()
        web = Aplicacion.objects.filter(nombre__icontains="web").first()
        siga = Aplicacion.objects.filter(nombre__icontains="SIGA").first()
        correo = Aplicacion.objects.filter(nombre__icontains="correo").first()
        for a, url in ((eva, "https://eva.istam.edu.ec"), (web, "https://www.istam.edu.ec"), (siga, "https://siga.istam.edu.ec")):
            if a and not a.url:
                a.url = url
                a.responsable = u["tic"]
                a.save()

        def ticket_app(app, solicitante, categoria, referencia, problema, prioridad, dias):
            t = servicios.crear_ticket_aplicacion(aplicacion=app, categoria=categoria, referencia=referencia, solicitante=solicitante,
                                                  creado_por=solicitante, problema=problema, prioridad=prioridad)
            Ticket.objects.filter(pk=t.pk).update(fecha=ahora - timedelta(days=dias))
            t.refresh_from_db()
            return t

        if eva and web and siga and correo:
            # 9. EVA - cerrado y resuelto
            t = ticket_app(eva, u["estudiante1"], "ACCESO", "Usuario 1912347596",
                           "No puedo ingresar al EVA, me dice que la contraseña es incorrecta y no me llega el correo para restablecerla.", "ALTA", 20)
            servicios.asignar(t, practicante=p1, tipo_soporte="APLICACION", prioridad="ALTA", por=admin)
            servicios.guardar_diagnostico(t, por=p1, datos=dict(
                descripcion="La cuenta estaba bloqueada por 5 intentos fallidos y el correo registrado en Moodle tenía un error de escritura.",
                causa="Correo mal registrado en el perfil.", recomendacion="Cambiar la contraseña al primer ingreso."))
            servicios.registrar_mantenimiento(t, por=p1, datos=dict(
                actividades="Desbloqueo de la cuenta, corrección del correo del perfil y restablecimiento de la contraseña temporal.",
                repuestos="Administración del sitio > Usuarios"))
            servicios.registrar_resultado(t, resultado="RESUELTO", detalle="El estudiante ingresó correctamente con la contraseña temporal.", por=p1)
            servicios.cerrar(t, por=u["tic"])

            # 10. EVA - atendido, matriculación
            t = ticket_app(eva, u["docente2"], "CURSOS", "Curso: Fundamentos de Enfermería - 2do A",
                           "Necesito que se matricule a 3 estudiantes nuevos en mi curso y que se habilite la tarea de la unidad 2.", "MEDIA", 9)
            servicios.asignar(t, practicante=p2, tipo_soporte="APLICACION", prioridad="MEDIA", por=admin)
            servicios.guardar_diagnostico(t, por=p2, datos=dict(
                descripcion="Los estudiantes no estaban sincronizados desde la matrícula del SIGA; la tarea tenía fecha de apertura futura.",
                causa="Matrícula tardía.", recomendacion=""))
            servicios.registrar_mantenimiento(t, por=p2, datos=dict(
                actividades="Matriculación manual de 3 estudiantes como alumnos y ajuste de la fecha de apertura de la tarea.", repuestos=""))
            servicios.registrar_resultado(t, resultado="RESUELTO", detalle="Estudiantes matriculados y tarea visible.", por=p2)

            # 11. Sitio web - en proceso
            t = ticket_app(web, u["tic"], "CONTENIDO", "https://www.istam.edu.ec/noticias",
                           "Publicar la noticia de la casa abierta con 4 fotografías y actualizar el banner principal.", "MEDIA", 3)
            servicios.asignar(t, practicante=p1, tipo_soporte="APLICACION", prioridad="MEDIA", por=admin)
            servicios.guardar_diagnostico(t, por=p1, datos=dict(
                descripcion="Las fotografías pesan 8 MB cada una y superan el límite de carga de WordPress.",
                causa="Imágenes sin optimizar.", recomendacion="Enviar imágenes de máximo 1 MB."))

            # 12. SIGA - escalado
            t = ticket_app(siga, u["docente1"], "ERROR", "Carrera de Contabilidad, 3er semestre",
                           "Al guardar las notas del segundo parcial aparece 'Error 500' y no se registran.", "URGENTE", 6)
            servicios.asignar(t, practicante=p2, tipo_soporte="APLICACION", prioridad="URGENTE", por=admin)
            servicios.guardar_diagnostico(t, por=p2, datos=dict(
                descripcion="El error ocurre para todas las materias del período; el registro del servidor muestra un fallo en el módulo de calificaciones.",
                causa="Falla del módulo del proveedor.", recomendacion="Registrar las notas en la plantilla de Excel mientras se corrige."))
            servicios.registrar_mantenimiento(t, por=p2, datos=dict(
                actividades="Verificación en varias materias, captura del error y reporte al proveedor del SIGA.", repuestos="Ticket del proveedor N.º 4471"))
            servicios.registrar_resultado(t, resultado="ESCALADO", detalle="Se reportó al proveedor; se informará cuando esté corregido.", por=p2)

            # 13 y 14. Pendientes de asignar
            ticket_app(correo, u["estudiante2"], "CUENTA", "Gabriela Loján - Administración",
                       "Soy estudiante nueva y aún no tengo correo institucional.", "MEDIA", 1)
            ticket_app(eva, u["docente1"], "ASESORIA", "",
                       "Solicito capacitación para crear cuestionarios con banco de preguntas en el EVA.", "BAJA", 0)

        # Fechas del historial y de los trabajos acordes a la fecha del ticket
        for t in Ticket.objects.all():
            paso = 0
            for h in t.historial.order_by("pk"):
                Historial.objects.filter(pk=h.pk).update(fecha=t.fecha + timedelta(hours=paso * 5))
                paso += 1
            cambios = {}
            if t.fecha_asignacion:
                cambios["fecha_asignacion"] = t.fecha + timedelta(hours=5)
            if t.fecha_atencion:
                cambios["fecha_atencion"] = t.fecha + timedelta(hours=(paso - 1 - (t.estado == "CERRADO")) * 5)
            if t.fecha_cierre:
                cambios["fecha_cierre"] = t.fecha + timedelta(hours=(paso - 1) * 5)
            Ticket.objects.filter(pk=t.pk).update(**cambios)
            d = t.diagnostico_o_none()
            if d:
                type(d).objects.filter(pk=d.pk).update(fecha=t.fecha + timedelta(hours=10))
            Mantenimiento.objects.filter(ticket=t).update(fecha=t.fecha + timedelta(hours=15))

        self.stdout.write(self.style.SUCCESS(f"Datos de prueba cargados. Contraseña de todos los usuarios: {CLAVE}"))
        for usuario, rol, *_ in USUARIOS:
            self.stdout.write(f"  {usuario:<13} {Usuario.Rol(rol).label:<20} cédula {u[usuario].cedula}")
