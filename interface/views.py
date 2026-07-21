"""
Views do app interface — servem apenas o "shell" HTML de cada tela.
"""
from pathlib import Path

from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


def saude(request):
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


def tela_gerenciar_usuarios(request):
    """
    Tela unica de gestao de pessoas -- unifica o que antes eram as
    telas separadas "Gerenciar Usuarios" e "Gerenciar Colaboradores".
    """
    return render(request, 'interface/gerenciar_usuarios.html')


def tela_novo_rad(request):
    return render(request, 'interface/novo_rad.html')


def service_worker(request):
    caminho = Path(__file__).resolve().parent / 'service_worker_src.js'
    return HttpResponse(caminho.read_text(), content_type='application/javascript')
