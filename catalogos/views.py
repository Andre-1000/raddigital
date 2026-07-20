"""
Views do app catalogos.

Um unico endpoint que devolve TODOS os catalogos de uma vez, pensado
para o cliente offline-first: em vez de 9 requisicoes separadas na
abertura da ferramenta (RG conforme PADROES_E_DIRETRIZES 5.2 --
"catalogos armazenados localmente, atualizados na abertura com
conexao"), uma unica chamada popula o IndexedDB inteiro.
"""
from django.http import JsonResponse

from usuarios.decorators import requer_token

from .models import (
    CatAcaoAmv,
    CatEquipe,
    CatLinha,
    CatLocal,
    CatMch,
    CatMotivoAtraso,
    CatServico,
    CatTipoDefeitoAmv,
    CatTipoManutencao,
    CatVia,
)


@requer_token
def listar_todos(request):
    """
    GET /catalogos/todos/
    Disponivel a qualquer usuario autenticado. So retorna registros
    ativos onde o catalogo tem esse conceito (itens inativos nao
    aparecem para selecao, mas continuam existindo para RADs antigos).
    """
    dados = {
        'linhas': list(CatLinha.objects.values('codigo', 'nome')),
        'locais': list(CatLocal.objects.values('sigla', 'nome', 'categoria')),
        'vias': list(CatVia.objects.values('id', 'nome')),
        'equipes': list(CatEquipe.objects.values('codigo', 'nome')),
        'tipos_manutencao': list(CatTipoManutencao.objects.values('id', 'nome')),
        'servicos': list(
            CatServico.objects.filter(ativo=True).values(
                'id', 'nome', 'descricao', 'requer_amv', 'requer_descricao'
            )
        ),
        'motivos_atraso': list(
            CatMotivoAtraso.objects.values('id', 'nome', 'requer_descricao')
        ),
        'mch': list(
            CatMch.objects.values(
                'id', 'identificacao', 'modelo', 'via', 'ur', 'local_amv', 'linha'
            )
        ),
        'tipos_defeito_amv': list(
            CatTipoDefeitoAmv.objects.filter(ativo=True).values('id', 'nome')
        ),
        'acoes_amv': list(CatAcaoAmv.objects.filter(ativo=True).values('id', 'nome')),
    }
    return JsonResponse(dados)
