"""
Funcao central de consulta: quais campos estao desabilitados agora.

Usada por rad/validadores.py (para deixar de exigir campos
desabilitados) e consulta/views.py (para nao exibi-los). Um unico ponto
de leitura evita que a regra "desabilitado = invisivel para todos" seja
reimplementada de formas diferentes em cada lugar.
"""
from .models import CampoFormulario

# 29/10/2026: campos com regra FIXA, que o Administrador NAO pode mais
# desabilitar nem tornar opcional na tela de Configuracoes:
#   - OS: obrigatoria em todo RAD. Marcar como opcional deixava o RAD
#     passar sem OS e o banco recusava -> erro 500 na sincronizacao (o
#     Nº de execucao e calculado a partir da OS, e a coluna nao aceita
#     vazio).
#   - N° SA: a obrigatoriedade passou a depender do Tipo de Manutencao
#     (obrigatoria em Preventiva/Preditiva, opcional em Corretiva,
#     inativa em Falha -- ver rad/validadores.py::_validar_numero_sa).
# O que estiver gravado em CampoFormulario para essas chaves e ignorado.
CAMPOS_REGRA_FIXA = frozenset({'numero_os', 'numero_sa'})


def campos_desabilitados():
    """Retorna o conjunto de chaves (str) de campos atualmente desabilitados."""
    return set(
        CampoFormulario.objects.filter(habilitado=False).values_list('chave', flat=True)
    ) - CAMPOS_REGRA_FIXA
