"""
Configuración del Sistema de Soporte de Equipos Informáticos - ISTAM.
Los valores sensibles se leen del archivo .env (copie .env.example como .env).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env(ruta):
    """Lee un archivo .env sencillo (CLAVE=valor) sin dependencias externas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(BASE_DIR / ".env")


def env(clave, defecto=""):
    return os.environ.get(clave, defecto)


def env_bool(clave, defecto=False):
    return env(clave, str(defecto)).lower() in ("1", "true", "si", "sí", "yes")


def env_lista(clave, defecto=""):
    return [x.strip() for x in env(clave, defecto).split(",") if x.strip()]


SECRET_KEY = env("SECRET_KEY", "django-insecure-cambie-esta-clave-en-produccion")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_lista("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_lista("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "cuentas",
    "equipos",
    "aplicaciones",
    "soporte",
    "reportes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cuentas.context_processors.institucion",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------- Base de datos ----------------
# Vacío = SQLite (ideal para desarrollo). "mysql" o "postgres" para el servidor.
DB_ENGINE = env("DB_ENGINE").lower()
if DB_ENGINE in ("mysql", "postgres", "postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql" if DB_ENGINE == "mysql" else "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "soporte_istam"),
            "USER": env("DB_USER", "root"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "3306" if DB_ENGINE == "mysql" else "5432"),
        }
    }
    if DB_ENGINE == "mysql":
        DATABASES["default"]["OPTIONS"] = {"charset": "utf8mb4"}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "cuentas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "es-ec"
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = False

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 horas

# ---------------- Correo ----------------
# Sin configurar, los avisos se imprimen en la terminal.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "soporte@istam.edu.ec")

# ---------------- Seguridad en producción ----------------
if env_bool("USAR_HTTPS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ---------------- Datos de la institución ----------------
INSTITUCION_NOMBRE = env("INSTITUCION_NOMBRE", "INSTITUTO SUPERIOR TECNOLÓGICO AMAZÓNICO")
INSTITUCION_SIGLAS = env("INSTITUCION_SIGLAS", "ISTAM")
INSTITUCION_CIUDAD = env("INSTITUCION_CIUDAD", "Yantzaza")
DEPARTAMENTO_TIC = env("DEPARTAMENTO_TIC", "Departamento de Tecnologías de la Información y Comunicación")

# Roles que pueden ver los reportes (según el documento: Administrador y Practicante).
# Para que el Responsable de TIC también los vea, agregue TIC a la lista en el .env: ROLES_REPORTES=ADMIN,PRACTICANTE,TIC
ROLES_REPORTES = env_lista("ROLES_REPORTES", "ADMIN,PRACTICANTE")

AUTHENTICATION_BACKENDS = ["cuentas.backends.UsuarioOCedulaBackend"]

# El primero es el cifrado normal; el segundo solo se usa en la carga masiva de usuarios
# y se reemplaza por el primero cuando el usuario inicia sesión.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "cuentas.hashers.PBKDF2ImportacionHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Carga masiva de usuarios
IMPORTAR_MAX_FILAS = 3000
