"""
Views do app colaboradores.

- buscar: disponivel a qualquer usuario autenticado, usada durante o
  preenchimento do RAD para localizar colaboradores (RG-RESP-003).
- listar_todos: devolve todos os colaboradores ativos de uma vez, para
  o cliente offline-first guardar em IndexedDB e poder adicionar
  colaboradores ao RAD mesmo sem conexao (o mesmo padrao usado em
  catalogos/views.py::listar_todos).
- criar/editar/excluir: exclusivas do Administrador (RG-RESP-012).
"""
import json
import re

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import UsuarioPerfil

from .models import ColaboradorCadastro

REGEX_SOMENTE_NUMEROS = re.compile(r'^\d+$')


def _serializar(colaborador):
    return {
        'id': colaborador.id,
        'registro_empresa': colaborador.registro_empresa,
        'nome': colaborador.nome,
        'ativo': colaborador.ativo,
    }


@requer_token
def listar_todos(request):
    """
    GET /colaboradores/todos/
    So retorna colaboradores ativos (RG conforme buscar -- inativos nao
    aparecem para selecao, so continuam existindo para RADs antigos).
    """
    colaboradores = ColaboradorCadastro.objects.filter(ativo=True).values(
        'registro_empresa', 'nome'
    )
    return JsonResponse({'colaboradores': list(colaboradores)})


@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def listar_para_administrar(request):
    """
    GET /colaboradores/administrar/
    Exclusivo do Administrador (RG-RESP-012). Ao contrario de
    listar_todos/buscar, inclui colaboradores INATIVOS tambem -- e a
    unica forma de ve-los para poder reativa-los ou editar antes de
    excluir de vez.
    """
    colaboradores = ColaboradorCadastro.objects.all().order_by('nome')
    return JsonResponse({'colaboradores': [_serializar(c) for c in colaboradores]})


@requer_token
def buscar(request):
    """
    GET /colaboradores/buscar/?q=texto
    RG-RESP-003: localiza por Registro da Empresa ou Nome.
    RG-RESP-008: se nada for encontrado, o cliente exibe "Colaborador
    nao localizado." -- aqui apenas retornamos lista vazia, a mensagem
    e responsabilidade da camada de apresentacao.
    Somente colaboradores ativos aparecem na pesquisa.
    """
    termo = (request.GET.get('q') or '').strip()
    if not termo:
        return JsonResponse({'resultados': []})

    resultados = ColaboradorCadastro.objects.filter(ativo=True).filter(
        Q(registro_empresa__icontains=termo) | Q(nome__icontains=termo)
    )[:20]

    return JsonResponse({'resultados': [_serializar(c) for c in resultados]})


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def criar(request):
    """
    POST /colaboradores/
    Body: {"registro_empresa": "12345", "nome": "Fulano de Tal"}
    RG-RESP-002: registro_empresa deve conter apenas numeros.
    RG-RESP-012: exclusivo do Administrador.
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    registro_empresa = (dados.get('registro_empresa') or '').strip()
    nome = (dados.get('nome') or '').strip()

    erros = _validar_registro_e_nome(registro_empresa, nome)
    if erros:
        return JsonResponse({'erros': erros}, status=422)

    if ColaboradorCadastro.objects.filter(registro_empresa=registro_empresa).exists():
        return JsonResponse(
            {'erros': [{'campo': 'registro_empresa', 'mensagem': 'Este registro ja esta cadastrado.'}]},
            status=422,
        )

    colaborador = ColaboradorCadastro.objects.create(
        registro_empresa=registro_empresa, nome=nome
    )
    return JsonResponse(_serializar(colaborador), status=201)


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def editar(request, id_colaborador):
    """
    POST /colaboradores/<id>/editar/
    Body: {"registro_empresa": "...", "nome": "...", "ativo": true}
    RG-RESP-011: RADs ja sincronizados preservam a copia historica --
    editar aqui NUNCA altera rad_colaboradores.
    """
    try:
        colaborador = ColaboradorCadastro.objects.get(id=id_colaborador)
    except ColaboradorCadastro.DoesNotExist:
        return JsonResponse({'erro': 'Colaborador nao encontrado.'}, status=404)

    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    registro_empresa = (dados.get('registro_empresa') or colaborador.registro_empresa).strip()
    nome = (dados.get('nome') or colaborador.nome).strip()

    erros = _validar_registro_e_nome(registro_empresa, nome)
    if erros:
        return JsonResponse({'erros': erros}, status=422)

    if (
        registro_empresa != colaborador.registro_empresa
        and ColaboradorCadastro.objects.filter(registro_empresa=registro_empresa).exists()
    ):
        return JsonResponse(
            {'erros': [{'campo': 'registro_empresa', 'mensagem': 'Este registro ja esta cadastrado.'}]},
            status=422,
        )

    colaborador.registro_empresa = registro_empresa
    colaborador.nome = nome
    if 'ativo' in dados:
        colaborador.ativo = bool(dados['ativo'])
    colaborador.save(update_fields=['registro_empresa', 'nome', 'ativo'])

    return JsonResponse(_serializar(colaborador))


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def excluir(request, id_colaborador):
    """
    POST /colaboradores/<id>/excluir/
    RG-RESP-011: exclusao do cadastro oficial nao afeta RADs ja
    sincronizados (rad_colaboradores e uma copia independente).
    """
    try:
        colaborador = ColaboradorCadastro.objects.get(id=id_colaborador)
    except ColaboradorCadastro.DoesNotExist:
        return JsonResponse({'erro': 'Colaborador nao encontrado.'}, status=404)

    colaborador.delete()
    return JsonResponse({'removido': True})


def _validar_registro_e_nome(registro_empresa, nome):
    erros = []
    if not registro_empresa:
        erros.append({'campo': 'registro_empresa', 'mensagem': 'Informe o registro da empresa.'})
    elif not REGEX_SOMENTE_NUMEROS.match(registro_empresa):
        erros.append(
            {'campo': 'registro_empresa', 'mensagem': 'O registro da empresa deve conter apenas numeros.'}
        )
    if not nome:
        erros.append({'campo': 'nome', 'mensagem': 'Informe o nome do colaborador.'})
    return erros
