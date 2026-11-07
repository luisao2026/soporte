from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsuarioOCedulaBackend(ModelBackend):
    """Permite iniciar sesión con el nombre de usuario o con la cédula."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        Usuario = get_user_model()
        usuario = Usuario.objects.filter(Q(username__iexact=username.strip()) | Q(cedula=username.strip())).first()
        if usuario is None:
            Usuario().set_password(password)  # mismo tiempo de respuesta si no existe
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
