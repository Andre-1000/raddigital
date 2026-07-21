"""
Views do app colaboradores.

- buscar: disponivel a qualquer usuario autenticado, usada durante o
  preenchimento do RAD para localizar colaboradores (RG-RESP-003).
- listar_todos: devolve todos os colaboradores ativos de uma vez, para
  o cliente offline-first guardar em IndexedDB e poder adicionar
  colaboradores ao RAD mesmo sem conexao (o mesmo padrao usado em
  catalogos/views.py::listar_todos).
- criar/editar/excluir/importar: exclusivas do Administrador (RG-RESP-012).

Cada colaborador tem um login vinculado automaticamente, usando a
propria matricula como login (decisao do projeto: matricula = login).
Perfil padrao ao criar/importar: Usuario -- pode ser promovido depois
na tela de gestao de usuarios.
"""
import csv
import io
import json
import re

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import Usuario, UsuarioPerfil

from .models import ColaboradorCadastro

REGEX_SOMENTE_NUMEROS = re.compile(r'^\d+$')
TAMANHO_MAXIMO_IMPORTACAO_BYTES = 5 * 1024 * 1024  # 5MB


def _garantir_usuario(colaborador):
    """
    Garante que o colaborador tem um login vinculado com login =
    matricula. Se o login ja existir (import antigo, por exemplo) so
    vincula; se nao existir, cria com perfil Usuario padrao.
    Idempotente -- pode ser chamado toda vez que o colaborador e
    criado/editado sem duplicar nada.
    """
    if colaborador.usuario_id:
        return colaborador.usuario

    usuario, criado = Usuario.objects.get_or_create(
        login=colaborador.registro_empresa
    )
    if criado:
        UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)

    colaborador.usuario = usuario
    colaborador.save(update_fields=['usuario'])
    return usuario


def _serializar(colaborador):
    usuario = colaborador.usuario
    return {
        'id': colaborador.id,
        'registro_empresa': colaborador.registro_empresa,
        'nome': colaborador.nome,
        'ativo': colaborador.ativo,
        'login': usuario.login if usuario else None,
        'perfis': usuario.lista_perfis if usuario else [],
        'usuario_ativo': usuario.ativo if usuario else None,
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
    Exclusivo do Administrador (RG-RESP-012). Tela "Gestao de Pessoas":
    inclui colaboradores INATIVOS tambem, e ja traz login/perfis
    (select_related evita 1 query por linha).
    """
    colaboradores = (
        ColaboradorCadastro.objects.select_related('usuario')
        .prefetch_related('usuario__perfis')
        .all()
        .order_by('nome')
    )
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
    Cria automaticamente o login (matricula = login, perfil Usuario).
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

    with transaction.atomic():
        colaborador = ColaboradorCadastro.objects.create(
            registro_empresa=registro_empresa, nome=nome
        )
        _garantir_usuario(colaborador)

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

    Atencao: mudar a matricula NAO renomeia o login existente (login
    e o identificador de autenticacao, ver usuarios/views.py::editar).
    Se a matricula mudar e nao houver login com o novo valor, um novo
    login e criado; o antigo continua existindo, desvinculado.
    """
    try:
        colaborador = ColaboradorCadastro.objects.select_related('usuario').get(
            id=id_colaborador
        )
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

    matricula_mudou = registro_empresa != colaborador.registro_empresa

    colaborador.registro_empresa = registro_empresa
    colaborador.nome = nome
    if 'ativo' in dados:
        colaborador.ativo = bool(dados['ativo'])
    colaborador.save(update_fields=['registro_empresa', 'nome', 'ativo'])

    if matricula_mudou:
        colaborador.usuario = None
        colaborador.save(update_fields=['usuario'])
    _garantir_usuario(colaborador)

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
    O login vinculado NAO e excluido automaticamente -- fica orfao,
    e removido manualmente na tela de usuarios se necessario.
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


def _decodificar_csv(conteudo_bruto):
    """
    Tenta algumas codificacoes comuns, nessa ordem: UTF-8 com BOM
    (o que o Excel do Windows costuma gravar), UTF-8 puro, e Latin-1
    (fallback comum para planilhas antigas/exportadas com acentuacao
    em codificacao antiga). Retorna None se nenhuma funcionar.
    """
    for codificacao in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return conteudo_bruto.decode(codificacao)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _detectar_delimitador_csv(texto):
    """
    Excel em portugues do Brasil normalmente exporta CSV com ";" (o
    "," e reservado para separador decimal nas configuracoes
    regionais brasileiras) -- mas um CSV gerado em inglês/outros
    sistemas costuma vir com ",". Decide pelo que aparece mais na
    primeira linha, em vez de assumir um dos dois.
    """
    primeira_linha = texto.splitlines()[0] if texto.splitlines() else ''
    return ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def importar(request):
    """
    POST /colaboradores/importar/
    Multipart, campo "arquivo": um CSV com duas colunas por linha --
    registro_empresa (matricula), nome. Cabecalho e opcional
    (detectado automaticamente).

    Cada linha nova cria tambem o login (matricula = login) com
    perfil Usuario. Linhas ja existentes so atualizam nome/status,
    sem mexer no login ja vinculado.

    Comportamento "upsert", pensado para poder rodar de novo sempre
    que a empresa mandar uma lista atualizada, sem duplicar nem falhar.

    RG-RESP-012: exclusivo do Administrador, mesma regra dos outros
    endpoints deste app.
    """
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Envie um arquivo CSV no campo "arquivo".'}, status=400)

    if arquivo.size > TAMANHO_MAXIMO_IMPORTACAO_BYTES:
        return JsonResponse({'erro': 'Arquivo muito grande (limite de 5MB).'}, status=400)

    texto = _decodificar_csv(arquivo.read())
    if texto is None:
        return JsonResponse(
            {'erro': 'Nao foi possivel ler o arquivo. Salve como CSV (UTF-8) e tente novamente.'},
            status=400,
        )

    delimitador = _detectar_delimitador_csv(texto)
    todas_as_linhas = list(csv.reader(io.StringIO(texto), delimiter=delimitador))
    todas_as_linhas = [linha for linha in todas_as_linhas if any((c or '').strip() for c in linha)]

    if not todas_as_linhas:
        return JsonResponse({'erro': 'Arquivo vazio.'}, status=400)

    indice_inicio = 0
    primeira_coluna = (todas_as_linhas[0][0] if todas_as_linhas[0] else '').strip()
    if not REGEX_SOMENTE_NUMEROS.match(primeira_coluna):
        indice_inicio = 1  # primeira linha parece cabecalho, nao dado -- pula

    criados = 0
    atualizados = 0
    erros_linhas = []

    with transaction.atomic():
        for numero_linha, linha in enumerate(todas_as_linhas[indice_inicio:], start=indice_inicio + 1):
            registro_empresa = (linha[0] if len(linha) > 0 else '').strip()
            nome = (linha[1] if len(linha) > 1 else '').strip()

            erros_campo = _validar_registro_e_nome(registro_empresa, nome)
            if erros_campo:
                erros_linhas.append(
                    {'linha': numero_linha, 'mensagem': '; '.join(e['mensagem'] for e in erros_campo)}
                )
                continue

            colaborador, criado = ColaboradorCadastro.objects.update_or_create(
                registro_empresa=registro_empresa,
                defaults={'nome': nome, 'ativo': True},
            )
            _garantir_usuario(colaborador)

            if criado:
                criados += 1
            else:
                atualizados += 1

    return JsonResponse(
        {
            'criados': criados,
            'atualizados': atualizados,
            'total_processado': criados + atualizados,
            'erros': erros_linhas,
        }
    )
