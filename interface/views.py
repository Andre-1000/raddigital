"""
Views do app interface — servem apenas o "shell" HTML de cada tela.

Autenticacao e dados sao tratados no cliente (JS + localStorage +
fetch para as APIs ja existentes), nao aqui: o token fica em
localStorage, inacessivel a uma view Django comum renderizando uma
navegacao de pagina normal. Por isso estas views nao usam @requer_token
-- quem decide se a pessoa pode ver a pagina e o RadAuth.exigirSessao()
no JS de cada template, redirecionando para /entrar/ quando necessario.
"""
from pathlib import Path

from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


def saude(request):
    """
    GET /saude/ — health check para orquestradores de container/load
    balancers (Railway, Render, Kubernetes, etc.). Confirma que o banco
    esta acessivel, nao so que o processo Django respondeu.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok'})
    except Exception as erro:
        return JsonResponse({'status': 'erro', 'detalhe': str(erro)}, status=503)


def tela_login(request):
    return render(request, 'interface/login.html')


def tela_inicio(request):
    return render(request, 'interface/inicio.html')


def tela_consulta(request):
    return render(request, 'interface/consulta.html')


def tela_detalhe_rad(request, numero_rad):
    return render(request, 'interface/detalhe_rad.html', {'numero_rad': numero_rad})


def tela_gerenciar_colaboradores(request):
    return render(request, 'interface/gerenciar_colaboradores.html')


def tela_novo_rad(request):
    return render(request, 'interface/novo_rad.html')


def service_worker(request):
    """
    GET /sw.js — precisa ser servido na RAIZ do dominio (nao em
    /static/), porque o escopo de um Service Worker e limitado ao
    diretorio de onde ele e servido. Servindo em /static/interface/js/
    o SW so conseguiria controlar paginas dentro desse caminho -- nunca
    /entrar/, /inicio/, /novo-rad/, etc.
    """
    caminho = Path(__file__).resolve().parent / 'service_worker_src.js'
    return HttpResponse(caminho.read_text(), content_type='application/javascript')
