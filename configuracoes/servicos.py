"""
Funcao central de consulta: quais campos estao desabilitados agora.

Usada por rad/validadores.py (para deixar de exigir campos
desabilitados) e consulta/views.py (para nao exibi-los). Um unico ponto
de leitura evita que a regra "desabilitado = invisivel para todos" seja
reimplementada de formas diferentes em cada lugar.
"""
from .models import CampoFormulario


def campos_desabilitados():
    """Retorna o conjunto de chaves (str) de campos atualmente desabilitados."""
    return set(
        CampoFormulario.objects.filter(habilitado=False).values_list('chave', flat=True)
    )
