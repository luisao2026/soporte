# Sistema de Soporte de Equipos Informáticos – ISTAM

Sistema web en **Python + Django** para gestionar usuarios, el inventario de equipos informáticos, los
tickets de soporte técnico, diagnósticos, mantenimientos (preventivos y correctivos) y reportes del
Departamento de TIC.

## 1. Requisitos
- **Python 3.11 o superior**: https://www.python.org/downloads/ (al instalar marque *"Add Python to PATH"*)
- **Visual Studio Code** con las extensiones **Python** y **Django** (VS Code las sugiere al abrir la carpeta)

No necesita internet para funcionar: Bootstrap y los íconos vienen incluidos en `static/vendor`.

## 2. Instalación (Windows, en la terminal de VS Code: *Terminal → New Terminal*)
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_demo
python manage.py runserver
```
Abra **http://127.0.0.1:8000** en el navegador.

> En Mac/Linux use `python3` y `source venv/bin/activate`.
> También puede ejecutar con **F5** en VS Code (configuración "Django: runserver").
> Para volver a cargar los datos de prueba desde cero: `python manage.py cargar_demo --forzar`

## 3. Usuarios de prueba (contraseña: `istam2026`)
Puede ingresar con el usuario **o** con la cédula.

| Usuario | Rol | Qué puede hacer |
|---|---|---|
| admin | Administrador | Todo: usuarios, equipos, catálogos, tickets, asignaciones, reportes y panel `/admin` |
| tic | Responsable de TIC | Supervisa: ve todos los tickets y equipos, el panel de control y cierra tickets atendidos |
| practicante1, practicante2 | Practicante | Atiende sus tickets asignados: diagnóstico, mantenimiento, observaciones y resultado. Ve sus reportes |
| docente1, docente2 | Docente | Registra sus equipos y crea tickets de soporte |
| estudiante1, estudiante2 | Estudiante | Registra sus equipos y crea tickets de soporte |

Los usuarios nuevos que registra el administrador ingresan con **su cédula como usuario y contraseña** y
pueden cambiarla en *Mi perfil → Cambiar contraseña*.

### Carga masiva de usuarios
En **Usuarios → Carga masiva** el administrador puede registrar muchos usuarios a la vez:
1. Descargue la **plantilla de Excel** (trae listas desplegables para Rol y Género y una hoja de instrucciones).
2. Llene un usuario por fila: Cédula, Apellidos, Nombres, Correo y Rol son obligatorios; Celular, Dirección, Cargo y Género son opcionales.
3. Suba el archivo (.xlsx o .csv). Puede elegir un **rol por defecto** para las filas sin rol, y si desea **actualizar**
   los usuarios cuya cédula ya existe (si no, se omiten).
4. Revise la **vista previa**: muestra qué se creará, actualizará u omitirá y los errores de cada fila (cédula inválida
   o repetida, correo repetido, rol desconocido...). Las filas con error se pueden descargar en Excel para corregirlas.
5. Confirme. Cada usuario nuevo ingresa con su **cédula como usuario y contraseña**.

El sistema recupera el cero inicial que Excel quita a cédulas y celulares, y reconoce encabezados como «CI», «Email»,
«Teléfono» o «Sexo», así que también sirve una lista exportada de otro sistema. Máximo 3000 filas por archivo.

## 4. Proceso del soporte técnico
```
Registro del ticket → Asignación al practicante → Diagnóstico → Mantenimiento (preventivo / correctivo)
→ Resultado (reparado / no reparado / devolución) → Cierre del ticket
```
1. **Docente o estudiante** registra su equipo y crea el ticket (problema, tipo de soporte y prioridad).
   El número de ticket, la marca, el modelo y la serie se toman automáticamente. Un equipo solo puede tener un ticket abierto.
2. **Administrador** asigna el ticket a un practicante (puede cambiar el tipo de soporte y la prioridad). El equipo pasa a *En mantenimiento* y el practicante recibe un correo.
3. **Practicante** registra el **diagnóstico** (qué encontró, causa, si requiere mantenimiento preventivo o correctivo).
4. **Practicante** registra el o los **mantenimientos** realizados y las **observaciones**.
5. **Practicante** registra el **resultado**: el ticket queda *Atendido*, el equipo cambia a *Reparado*, *No reparado* o *Devuelto* y el solicitante recibe un correo.
6. **Administrador o Responsable de TIC** **cierra** el ticket.

El administrador también puede hacer el trabajo del practicante y **cambiar el estado** de un ticket
(por ejemplo, reabrirlo); todo queda en el **historial** del ticket. Cada ticket tiene un **Informe de
soporte técnico en PDF** con firmas.

### Estados
- **Ticket:** Pendiente, Asignado, En proceso, Atendido, Cerrado.
- **Equipo:** Activo, En mantenimiento, Reparado, No reparado, Devuelto, Dado de baja.

### Soporte a aplicaciones (EVA/Moodle, WordPress, SIGA, correo...)
Al crear un ticket se elige **Equipo informático** o **Aplicación o plataforma**. El ticket de aplicación usa los
mismos practicantes, estados, historial y avisos por correo, con estos cambios:

| Equipo | Aplicación |
|---|---|
| Equipo, marca, modelo, serie | Aplicación, tipo de solicitud y "usuario, curso o página afectada" |
| Diagnóstico | Análisis del problema |
| Mantenimiento preventivo / correctivo | Acciones realizadas en la aplicación |
| Reparado / No reparado / Devolución | Resuelto / No resuelto / Escalado al proveedor |
| El equipo cambia de estado | No afecta a ningún equipo |

Tipos de solicitud: acceso o contraseña, creación o activación de usuario, cursos/matrículas/permisos,
publicación de contenido, error del sistema, configuración, asesoría o capacitación.

El **catálogo de aplicaciones** (menú *Aplicaciones*) lo administra el Administrador: nombre, plataforma, URL,
responsable técnico y proveedor. Vienen registradas EVA (Moodle), Sitio web (WordPress), SIGA y Correo institucional;
puede agregar otras (biblioteca virtual, sistema de admisiones, etc.). El responsable técnico de una aplicación
recibe un correo cuando se crea un ticket para ella.

## 5. Reportes (Administrador y Practicante)
Todos se filtran por fechas y se exportan a **PDF** y **Excel**. El practicante solo ve lo que él atendió.
- **Tickets:** registrados, pendientes, asignados, atendidos y cerrados.
- **Diagnósticos:** equipo, usuario, problema, diagnóstico, técnico/practicante, fecha y resultado.
- **Equipos por mantenimiento:** preventivo y correctivo, por tipo de equipo.
- **Tipos de soporte:** cantidad de diagnósticos, mantenimientos preventivos y correctivos y soportes a aplicaciones, por practicante.
- **Soporte a aplicaciones:** solicitudes por aplicación, tipo de solicitud y resultado (resuelto, no resuelto, escalado).

> Si el Responsable de TIC también debe ver los reportes, en el archivo `.env` ponga `ROLES_REPORTES=ADMIN,PRACTICANTE,TIC`.

## 6. Estructura del proyecto
```
config/        Configuración (settings.py, urls.py)
cuentas/       Usuarios, roles, login (con usuario o cédula), perfil y carga masiva (importar.py)
equipos/       Equipos, categorías, marcas y modelos
aplicaciones/  Catálogo de aplicaciones (EVA/Moodle, WordPress, SIGA...)
soporte/       Tickets, diagnósticos, mantenimientos, observaciones e historial
   servicios.py   Reglas del proceso de soporte (asignar, diagnosticar, cerrar...)
   pdf.py         Informe de soporte técnico en PDF
   management/commands/cargar_demo.py   Datos de prueba
reportes/      Reportes en pantalla, PDF y Excel
templates/     Páginas HTML (Bootstrap 5)
static/        CSS con los colores institucionales, JS, Bootstrap local y los logos del ISTAM
```

## 7. Configuración (.env)
Copie `.env.example` como `.env`:
- **Logo:** ya viene incluido (`static/img/logo_istam.png`, `logo_icono.png` y `favicon.png`); para cambiarlo reemplace esos archivos.
- **Correo real (Gmail):** descomente las líneas `EMAIL_...` y use una *contraseña de aplicación* de Google.
  Sin configurar, los correos se muestran en la terminal.
- **MySQL:** `pip install mysqlclient`, cree la base `soporte_istam` y ponga `DB_ENGINE=mysql`.

## 8. Publicar en el servidor (Docker + PostgreSQL)
```bash
cp deploy/env.docker.example .env      # edite SECRET_KEY, dominio y contraseñas
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```
El sistema queda en `127.0.0.1:8082`; publique el dominio con Apache usando `deploy/apache-soporte.conf`.
