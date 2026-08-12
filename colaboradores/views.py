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
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import Usuario, UsuarioPerfil
from usuarios.views import REGEX_EMAIL_SIMPLES, _validar_perfis

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


def _status_senha(usuario):
    """
    30/07/2026. Tres estados possiveis, nesta ordem de prioridade:
    - 'pendente': sem senha definida ainda (usuario legado, ou recem
      criado sem passar por "Esqueci minha senha").
    - 'bloqueada': tem senha, mas esta temporariamente bloqueada por
      excesso de tentativas erradas (ver usuarios/views.py::login,
      settings.MAXIMO_TENTATIVAS_LOGIN). Prioridade sobre 'ativa' --
      mesmo com a senha certa, a pessoa nao consegue entrar agora.
    - 'ativa': tem senha definida e nao esta bloqueada.
    """
    if not usuario.senha_hash:
        return 'pendente'
    if usuario.bloqueado_ate and usuario.bloqueado_ate > timezone.now():
        return 'bloqueada'
    return 'ativa'


def _serializar(colaborador):
    usuario = colaborador.usuario
    return {
        'id': colaborador.id,
        'registro_empresa': colaborador.registro_empresa,
        'nome': colaborador.nome,
        'ativo': colaborador.ativo,
        'usuario_id': usuario.id if usuario else None,
        'login': usuario.login if usuario else None,
        # 30/07/2026: e-mail e status de senha, pra tela de Gestao de
        # Usuarios mostrar quem ainda nao consegue entrar no sistema
        # e permitir editar o e-mail necessario pro fluxo de "Esqueci
        # minha senha".
        'email': usuario.email if usuario else None,
        'status_senha': _status_senha(usuario) if usuario else 'pendente',
        'bloqueado_ate': (
            usuario.bloqueado_ate.isoformat()
            if usuario and usuario.bloqueado_ate else None
        ),
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
    Body: {"registro_empresa": "12345", "nome": "Fulano de Tal",
           "email": "fulano@empresa.com", "perfis": ["usuario"]}
    RG-RESP-002: registro_empresa deve conter apenas numeros.
    RG-RESP-012: exclusivo do Administrador.

    30/07/2026: e-mail passou a ser OBRIGATORIO no cadastro manual --
    sem ele a pessoa nunca conseguiria usar "Esqueci minha senha" pra
    criar a primeira senha, ficando cadastrada mas sem conseguir
    entrar no sistema. "perfis" e opcional (default: so Usuario).

    Cria automaticamente o login (matricula = login) e ja aplica
    e-mail/perfis na mesma chamada -- antes disso era um segundo POST
    separado em /usuarios/administrar/<id>/editar/, feito pelo cliente
    logo em seguida; unificado aqui para simplificar o fluxo e evitar
    o colaborador ficar num estado intermediario (criado mas sem
    e-mail) caso a segunda chamada falhasse por qualquer motivo.
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    registro_empresa = (dados.get('registro_empresa') or '').strip()
    nome = (dados.get('nome') or '').strip()
    email_informado = (dados.get('email') or '').strip().lower()
    perfis_solicitados = dados.get('perfis') or [UsuarioPerfil.USUARIO]

    erros = _validar_registro_e_nome(registro_empresa, nome)

    if not email_informado:
        erros.append({'campo': 'email', 'mensagem': 'Informe o e-mail.'})
    elif not REGEX_EMAIL_SIMPLES.match(email_informado):
        erros.append({'campo': 'email', 'mensagem': 'E-mail invalido.'})
    elif Usuario.objects.filter(email__iexact=email_informado).exists():
        erros.append({'campo': 'email', 'mensagem': 'Este e-mail ja esta em uso por outro usuario.'})

    if ColaboradorCadastro.objects.filter(registro_empresa=registro_empresa).exists():
        erros.append({'campo': 'registro_empresa', 'mensagem': 'Este registro ja esta cadastrado.'})

    erros_perfil, perfis_validos = _validar_perfis(perfis_solicitados, request.usuario_rad)
    erros.extend(erros_perfil)

    if erros:
        return JsonResponse({'erros': erros}, status=422)

    with transaction.atomic():
        colaborador = ColaboradorCadastro.objects.create(
            registro_empresa=registro_empresa, nome=nome
        )
        usuario = _garantir_usuario(colaborador)
        usuario.email = email_informado
        usuario.save(update_fields=['email'])
        usuario.perfis.all().delete()
        for p in perfis_validos:
            UsuarioPerfil.objects.create(usuario=usuario, perfil=p)

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
    Multipart, campo "arquivo": um CSV com 4 colunas, NESTA ORDEM --
    Nome, Matricula, Perfis, Email (30/07/2026, revisado). Cabecalho e
    opcional (detectado automaticamente).

    - Nome, Matricula: obrigatorios em toda linha.
    - Perfis: opcional. Quando vazio, aplica so "usuario". Quando
      preenchido, aceita mais de um perfil na mesma celula separado
      por virgula (ex.: "usuario,supervisor") -- por isso o
      delimitador do ARQUIVO deve ser ";" quando essa coluna for usada
      com mais de um perfil (ver _detectar_delimitador_csv). Valores
      aceitos: usuario, supervisor, administrador.
    - Email: opcional na importacao em lote (ao contrario do cadastro
      manual, onde e obrigatorio) -- listas grandes de colaboradores
      legados nem sempre tem e-mail de todo mundo already à mão;
      melhor permitir importar mesmo assim e completar depois, um por
      um, do que travar o lote inteiro.

    Cada linha nova cria tambem o login (matricula = login). Linhas ja
    existentes atualizam nome/perfis/email/status, sem duplicar.
    Comportamento "upsert" -- pode rodar de novo com uma lista
    atualizada sem duplicar nem falhar.

    RG-RESP-012: exclusivo do Administrador.
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

    # Deteccao de cabecalho: a coluna 2 (Matricula, indice 1) deve ser
    # numerica em linha de dado de verdade -- se nao for, a primeira
    # linha provavelmente e cabecalho ("Nome;Matricula;Perfis;Email").
    indice_inicio = 0
    segunda_coluna = (todas_as_linhas[0][1] if len(todas_as_linhas[0]) > 1 else '').strip()
    if not REGEX_SOMENTE_NUMEROS.match(segunda_coluna):
        indice_inicio = 1

    criados = 0
    atualizados = 0
    erros_linhas = []

    with transaction.atomic():
        for numero_linha, linha in enumerate(todas_as_linhas[indice_inicio:], start=indice_inicio + 1):
            nome = (linha[0] if len(linha) > 0 else '').strip()
            registro_empresa = (linha[1] if len(linha) > 1 else '').strip()
            perfis_texto = (linha[2] if len(linha) > 2 else '').strip()
            email_informado = (linha[3] if len(linha) > 3 else '').strip().lower()

            erros_campo = _validar_registro_e_nome(registro_empresa, nome)
            if email_informado and not REGEX_EMAIL_SIMPLES.match(email_informado):
                erros_campo.append({'campo': 'email', 'mensagem': 'E-mail invalido.'})
            if erros_campo:
                erros_linhas.append(
                    {'linha': numero_linha, 'mensagem': '; '.join(e['mensagem'] for e in erros_campo)}
                )
                continue

            perfis_lista = (
                [p.strip().lower() for p in perfis_texto.split(',') if p.strip()]
                if perfis_texto else [UsuarioPerfil.USUARIO]
            )
            _erros_perfil, perfis_validos = _validar_perfis(perfis_lista, request.usuario_rad)
            if _erros_perfil:
                # perfil invalido/nao permitido na linha -- nao trava o
                # lote inteiro, so cai pro padrao (Usuario) e segue.
                perfis_validos = [UsuarioPerfil.USUARIO]

            colaborador, criado = ColaboradorCadastro.objects.update_or_create(
                registro_empresa=registro_empresa,
                defaults={'nome': nome, 'ativo': True},
            )
            usuario = _garantir_usuario(colaborador)

            if email_informado and not Usuario.objects.filter(
                email__iexact=email_informado
            ).exclude(id=usuario.id).exists():
                usuario.email = email_informado
                usuario.save(update_fields=['email'])

            usuario.perfis.all().delete()
            for p in perfis_validos:
                UsuarioPerfil.objects.create(usuario=usuario, perfil=p)

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
