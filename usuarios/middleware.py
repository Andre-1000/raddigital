"""
Middleware de bloqueio do /admin/ por tentativas de login erradas
(30/07/2026, Seguranca A02 -- OWASP Top 10:2025).

O admin usa django.contrib.auth, que tem usuario/senha completamente
separados do login do Sistema RAD (usuarios.models.Usuario). Por isso
o rate limit aqui e por IP, nao por usuario -- funciona mesmo se a
tentativa usar um nome de usuario que nem existe (o caso mais comum de
bot escaneando paineis admin as cegas).
"""
from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils import timezone


def obter_ip_cliente(request):
    """
    Atras do proxy reverso do Render, o IP real do visitante vem no
    cabecalho X-Forwarded-For (pega o primeiro da lista, caso haja
    mais de um proxy encadeado) -- request.META['REMOTE_ADDR'] sozinho
    devolveria o IP interno do proxy do Render, o mesmo pra todo mundo.
    """
    encaminhado = request.META.get('HTTP_X_FORWARDED_FOR')
    if encaminhado:
        return encaminhado.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class BloqueioAdminMiddleware:
    """
    Bloqueia temporariamente qualquer acesso ao /admin/ (GET e POST)
    vindo de um IP que excedeu MAXIMO_TENTATIVAS_ADMIN logins errados
    seguidos. O contador em si e incrementado pelos sinais em
    usuarios/signals.py (user_login_failed/user_logged_in) -- este
    middleware so LE o estado e decide bloquear ou deixar passar, roda
    ANTES do Django tentar processar o formulario de login do admin.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        caminho_admin = f'/{settings.ADMIN_URL_PATH}/'
        if request.path.startswith(caminho_admin):
            from .models import TentativaLoginAdmin

            ip = obter_ip_cliente(request)
            tentativa = TentativaLoginAdmin.objects.filter(ip=ip).first()
            if tentativa and tentativa.bloqueado_ate and tentativa.bloqueado_ate > timezone.now():
                minutos_restantes = max(
                    1, int((tentativa.bloqueado_ate - timezone.now()).total_seconds() // 60) + 1
                )
                return HttpResponseForbidden(
                    f'Muitas tentativas de login incorretas. Tente novamente em {minutos_restantes} minuto(s).'
                )
        return self.get_response(request)
