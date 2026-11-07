from django.core.exceptions import ValidationError


def cedula_valida(cedula: str) -> bool:
    """Valida una cédula ecuatoriana (10 dígitos, provincia 01-24 o 30, dígito verificador módulo 10)."""
    if not cedula or len(cedula) != 10 or not cedula.isdigit():
        return False
    provincia = int(cedula[:2])
    if not (1 <= provincia <= 24 or provincia == 30):
        return False
    if int(cedula[2]) >= 6:
        return False
    suma = 0
    for i, d in enumerate(cedula[:9]):
        n = int(d) * (2 if i % 2 == 0 else 1)
        suma += n - 9 if n > 9 else n
    verificador = (10 - suma % 10) % 10
    return verificador == int(cedula[9])


def validar_cedula(valor):
    if not cedula_valida(valor):
        raise ValidationError("La cédula ingresada no es válida.")


def validar_celular(valor):
    if valor and (not valor.isdigit() or len(valor) != 10 or not valor.startswith("09")):
        raise ValidationError("El celular debe tener 10 dígitos y empezar con 09.")
