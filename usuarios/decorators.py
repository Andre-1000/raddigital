"""
Decoradores de autenticacao e autorizacao por token.

O Sistema RAD nao usa sessao/senha Django (RG-AUTH-001). A autenticacao
das rotas do servidor (sincronizacao, consulta, gestao) e feita via
token enviado no cabecalho:

    Authorization: Token <valor-do-token>

Referencia: EFD secao 3.9 (AUTENTICACAO) e secao 4 (MATRIZ DE PERMISSOES).
"""
import functools

from django.http import JsonResponse

from .models import Token


def _extrair_token(request):
    cabecalho = request.headers.get('Authorization', '')
    if not cabecalho.startswith('Token '):
        return None
    return cabecalho.removeprefix('Token ').strip()


def requer_token(view_func):
    """
    Exige um token valido e nao expirado (RG-AUTH-008). Anexa o usuario
    autenticado em request.usuario_rad para uso na view.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        valor_token = _extrair_token(request)
        if not valor_token:
            return JsonResponse(
                {'erro': 'Token de autenticacao ausente.'}, status=401
            )

        try:
            token = Token.objects.select_related('usuario').get(token=valor_token)
        except Token.DoesNotExist:
            return JsonResponse({'erro': 'Token invalido.'}, status=401)

        if token.expirado:
            return JsonResponse(
                {'erro': 'Sua sessao expirou. Conecte-se para continuar.'},
                status=401,
            )

        if not token.usuario.ativo:
            return JsonResponse({'erro': 'Usuario inativo.'}, status=403)

        request.usuario_rad = token.usuario
        request.token_rad = token
        return view_func(request, *args, **kwargs)

    return wrapper


def requer_perfil(*perfis_permitidos):
    """
    Exige que o usuario autenticado (ja validado por requer_token) possua
    ao menos um dos perfis informados. Combina com @requer_token:

        @requer_token
        @requer_perfil('supervisor', 'administrador')
        def minha_view(request): ...
    """

    def decorador(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            usuario = getattr(request, 'usuario_rad', None)
            if usuario is None:
                return JsonResponse(
                    {'erro': 'Autenticacao necessaria.'}, status=401
                )
            perfis_usuario = set(usuario.lista_perfis)
            if not perfis_usuario.intersection(perfis_permitidos):
                return JsonResponse(
                    {'erro': 'Acesso nao autorizado para o seu perfil.'},
                    status=403,
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorador
