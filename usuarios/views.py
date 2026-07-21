"""
Views do app usuarios.

Login sem senha (RG-AUTH-001/003). Gestao de usuarios (EFD secao 4.4).
Supervisor gerencia Usuarios e Supervisores (PRM-015 a PRM-020).
Administrador gerencia todos (PRM-021 a PRM-024).
"""
import json
import re

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from .decorators import requer_perfil, requer_token
from .models import Token, Usuario, UsuarioPerfil

REGEX_LOGIN = re.compile(r'^[a-zA-Z0-9_.@-]{3,100}$')


# ---------------------------------------------------------------------------
# Autenticacao
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def login(request):
    """
    POST /usuarios/login/
    Body: {"login": "joao.silva", "dispositivo": "opcional"}
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    login_informado = (dados.get('login') or '').strip()
    if not login_informado:
        return JsonResponse({'erro': 'Informe o login.'}, status=400)

    try:
        usuario = Usuario.objects.get(login=login_informado)
    except Usuario.DoesNotExist:
        return JsonResponse({'erro': 'Login nao encontrado.'}, status=401)

    if not usuario.ativo:
        return JsonResponse({'erro': 'Usuario inativo.'}, status=401)

    token = Token.gerar_para(usuario, dispositivo=dados.get('dispositivo'))

    return JsonResponse(
        {
            'token': token.token,
            'validade': token.validade.isoformat(),
            'login': usuario.login,
            'perfis': usuario.lista_perfis,
        },
        status=200,
    )


@requer_token
def validar_token(request):
    """
    GET /usuarios/validar-token/
    """
    usuario = request.usuario_rad
    return JsonResponse(
        {
            'login': usuario.login,
            'perfis': usuario.lista_perfis,
            'validade': request.token_rad.validade.isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Gestao de usuarios (EFD secao 4.4)
# ---------------------------------------------------------------------------

def _pode_gerenciar(usuario_alvo, usuario_solicitante):
    """
    Supervisor nao pode gerenciar usuarios com perfil EXCLUSIVO de
    Administrador (PRM-016/017). Administrador pode gerenciar todos.
    """
    if usuario_solicitante.tem_perfil(UsuarioPerfil.ADMINISTRADOR):
        return True
    perfis_alvo = set(usuario_alvo.lista_perfis)
    return perfis_alvo != {UsuarioPerfil.ADMINISTRADOR}


def _serializar_usuario(usuario, usuario_solicitante=None):
    dados = {
        'id': usuario.id,
        'login': usuario.login,
        'ativo': usuario.ativo,
        'perfis': usuario.lista_perfis,
        'data_criacao': usuario.data_criacao.strftime('%d/%m/%Y'),
    }
    if usuario_solicitante is not None:
        dados['pode_gerenciar'] = _pode_gerenciar(usuario, usuario_solicitante)
    return dados


@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def listar(request):
    """
    GET /usuarios/administrar/
    Retorna TODOS os usuarios. O campo pode_gerenciar indica ao cliente
    se o solicitante tem permissao de editar/excluir cada usuario.
    Supervisor ve admins na lista mas nao pode gerencia-los (PRM-016/017).
    """
    solicitante = request.usuario_rad
    usuarios = Usuario.objects.prefetch_related('perfis').order_by('login')
    return JsonResponse({
        'usuarios': [_serializar_usuario(u, solicitante) for u in usuarios]
    })


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def criar(request):
    """
    POST /usuarios/administrar/criar/
    Body: {"login": "joao.silva", "perfis": ["usuario"]}
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    login_novo = (dados.get('login') or '').strip()
    perfis_solicitados = list(set(dados.get('perfis') or []))
    solicitante = request.usuario_rad

    erros = []

    if not login_novo:
        erros.append({'campo': 'login', 'mensagem': 'Informe o login.'})
    elif not REGEX_LOGIN.match(login_novo):
        erros.append({'campo': 'login', 'mensagem': 'Login invalido. Use letras, numeros, pontos, hifens ou underline (minimo 3 caracteres).'})
    elif Usuario.objects.filter(login=login_novo).exists():
        erros.append({'campo': 'login', 'mensagem': 'Este login ja esta em uso.'})

    erros_perfil, perfis_validos = _validar_perfis(perfis_solicitados, solicitante)
    erros.extend(erros_perfil)

    if erros:
        return JsonResponse({'erros': erros}, status=422)

    with transaction.atomic():
        usuario = Usuario.objects.create(login=login_novo)
        for p in perfis_validos:
            UsuarioPerfil.objects.create(usuario=usuario, perfil=p)

    return JsonResponse(_serializar_usuario(usuario, solicitante), status=201)


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def editar(request, id_usuario):
    """
    POST /usuarios/administrar/<id>/editar/
    Body: {"perfis": [...], "ativo": true}
    Login nao e editavel apos a criacao -- e o identificador de
    autenticacao e alterar causaria confusao operacional.
    """
    try:
        usuario = Usuario.objects.prefetch_related('perfis').get(id=id_usuario)
    except Usuario.DoesNotExist:
        return JsonResponse({'erro': 'Usuario nao encontrado.'}, status=404)

    solicitante = request.usuario_rad
    if not _pode_gerenciar(usuario, solicitante):
        return JsonResponse(
            {'erro': 'Voce nao tem permissao para editar este usuario.'},
            status=403,
        )

    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    perfis_solicitados = list(set(dados.get('perfis', usuario.lista_perfis)))
    erros, perfis_validos = _validar_perfis(perfis_solicitados, solicitante)

    if erros:
        return JsonResponse({'erros': erros}, status=422)

    with transaction.atomic():
        if 'ativo' in dados:
            usuario.ativo = bool(dados['ativo'])
            usuario.save(update_fields=['ativo'])
        usuario.perfis.all().delete()
        for p in perfis_validos:
            UsuarioPerfil.objects.create(usuario=usuario, perfil=p)

    usuario.refresh_from_db()
    return JsonResponse(_serializar_usuario(usuario, solicitante))


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def excluir(request, id_usuario):
    """
    POST /usuarios/administrar/<id>/excluir/
    """
    try:
        usuario = Usuario.objects.prefetch_related('perfis').get(id=id_usuario)
    except Usuario.DoesNotExist:
        return JsonResponse({'erro': 'Usuario nao encontrado.'}, status=404)

    solicitante = request.usuario_rad

    if usuario.id == solicitante.id:
        return JsonResponse(
            {'erro': 'Nao e possivel excluir o proprio usuario.'},
            status=403,
        )

    if not _pode_gerenciar(usuario, solicitante):
        return JsonResponse(
            {'erro': 'Voce nao tem permissao para excluir este usuario.'},
            status=403,
        )

    usuario.delete()
    return JsonResponse({'removido': True})


def _validar_perfis(perfis_solicitados, usuario_solicitante):
    perfis_validos_set = {UsuarioPerfil.USUARIO, UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR}
    erros = []

    for p in perfis_solicitados:
        if p not in perfis_validos_set:
            erros.append({'campo': 'perfis', 'mensagem': f'Perfil invalido: {p}.'})

    if len(perfis_solicitados) > 2:
        erros.append({'campo': 'perfis', 'mensagem': 'Maximo de 2 perfis por usuario.'})

    if not perfis_solicitados:
        erros.append({'campo': 'perfis', 'mensagem': 'Selecione ao menos 1 perfil.'})

    eh_admin = usuario_solicitante.tem_perfil(UsuarioPerfil.ADMINISTRADOR)
    if not eh_admin and UsuarioPerfil.ADMINISTRADOR in perfis_solicitados:
        erros.append({
            'campo': 'perfis',
            'mensagem': 'Supervisor nao pode atribuir o perfil Administrador (PRM-024).',
        })

    return erros, perfis_solicitados
