"""
Sinais de autenticacao do Django admin (30/07/2026, Seguranca A02).

Usa os sinais nativos do django.contrib.auth -- user_login_failed
dispara em TODA tentativa de login errada em qualquer lugar que use o
sistema de auth do Django (aqui, so o /admin/ usa isso; o login do
Sistema RAD tem seu proprio mecanismo em usuarios/views.py::login, ja
com rate limit proprio). user_logged_in dispara em todo login correto.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.utils import timezone

from .middleware import obter_ip_cliente
from .models import TentativaLoginAdmin


@receiver(user_login_failed)
def registrar_tentativa_falha(sender, credentials, request=None, **kwargs):
    if request is None:
        return
    ip = obter_ip_cliente(request)
    maximo = getattr(settings, 'MAXIMO_TENTATIVAS_ADMIN', 5)
    minutos_bloqueio = getattr(settings, 'BLOQUEIO_ADMIN_MINUTOS', 15)

    tentativa, _criado = TentativaLoginAdmin.objects.get_or_create(ip=ip)
    tentativa.tentativas += 1
    if tentativa.tentativas >= maximo:
        tentativa.bloqueado_ate = timezone.now() + timedelta(minutes=minutos_bloqueio)
    tentativa.save()


@receiver(user_logged_in)
def limpar_tentativas(sender, request=None, **kwargs):
    if request is None:
        return
    ip = obter_ip_cliente(request)
    TentativaLoginAdmin.objects.filter(ip=ip).update(tentativas=0, bloqueado_ate=None)
