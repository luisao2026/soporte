from django.core.paginator import Paginator


def paginar(request, queryset, por_pagina=15):
    """Devuelve la página solicitada y la cadena de filtros actuales (sin 'page') para los enlaces."""
    pagina = Paginator(queryset, por_pagina).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return pagina, params.urlencode()
