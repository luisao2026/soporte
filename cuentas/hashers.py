from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PBKDF2ImportacionHasher(PBKDF2PasswordHasher):
    """
    Cifrado para la contraseña inicial (la cédula) de los usuarios creados por carga masiva.

    Usa menos iteraciones para poder crear cientos de usuarios en segundos. Como tiene un nombre
    de algoritmo distinto, Django lo reemplaza por el cifrado normal (más fuerte) automáticamente
    la primera vez que el usuario inicia sesión.
    """

    algorithm = "pbkdf2_sha256_importacion"
    iterations = 20_000
