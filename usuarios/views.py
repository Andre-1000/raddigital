"""
Views de autenticacao do Sistema RAD.

Login sem senha (RG-AUTH-001): o usuario informa apenas o login. Se o
login existir e estiver ativo, o servidor gera um token valido por
VALIDADE_TOKEN_DIAS dias (RG-AUTH-003) que o cliente guarda localmente
(IndexedDB) para uso offline (RG-AUTH-007).

O logout automatico ao fechar o app (RG-AUTH-005) e tratado no
frontend/Service Worker — o token continua valido no servidor
(RG-AUTH-006), apenas a tela volta a pedir o login.
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .decorators import requer_token
from .models import Token, Usuario


@csrf_exempt
@require_POST
def login(request):
    """
    POST /usuarios/login/
    Body: {"login": "joao.silva", "dispositivo": "opcional"}

    Retorna o token e os perfis do usuario quando o login e valido
    (RG-AUTH-003). Recusa quando o login nao existe ou esta inativo
    (RG-AUTH-001/AUTH-002).
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
    Usado pelo cliente para confirmar (quando ha conexao) que o token
    salvo localmente ainda e valido, e para obter os perfis atualizados.
    Quando offline, o cliente valida a validade localmente sem chamar
    esta rota (RG-AUTH-007).
    """
    usuario = request.usuario_rad
    return JsonResponse(
        {
            'login': usuario.login,
            'perfis': usuario.lista_perfis,
            'validade': request.token_rad.validade.isoformat(),
        }
    )
