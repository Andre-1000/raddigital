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


def tela_meus_rads(request):
    """
    Tela "RADs Preenchidos" (22/07/2026) -- qualquer usuario logado,
    sempre filtrada ao proprio login (ver consulta/views.py::listar_meus_rads).
    """
    return render(request, 'interface/meus_rads.html')


def tela_gerenciar_usuarios(request):
    """
    Tela unica de gestao de pessoas -- unifica o que antes eram as
    telas separadas "Gerenciar Usuarios" e "Gerenciar Colaboradores".
    """
    return render(request, 'interface/gerenciar_usuarios.html')


def tela_configuracoes(request):
    """
    Tela "Configurações de Campos" (22/07/2026) -- exclusiva do
    Administrador. Alternar habilitado/obrigatorio de cada campo do
    formulario. O acesso e checado no proprio JS da tela (mesmo padrao
    de tela_consulta) -- o guard real esta nos endpoints da API
    (configuracoes/views.py, @requer_perfil(ADMINISTRADOR)).
    """
    return render(request, 'interface/configuracoes.html')


def tela_dashboard(request):
    """
    28/08/2026. Painel com números e gráficos agregados sobre RADs
    sincronizados -- Supervisor e Administrador (mesmo padrão de
    tela_consulta). O guard real está nos endpoints da API
    (dashboard/views.py, @requer_perfil(SUPERVISOR, ADMINISTRADOR)).
    """
    return render(request, 'interface/dashboard.html')


def tela_novo_rad(request):
    return render(request, 'interface/novo_rad.html')


def tela_redefinir_senha(request):
    """
    Pagina PUBLICA (sem autenticacao, 30/07/2026) -- destino do link de
    e-mail do fluxo "Esqueci minha senha". O token vem via query string
    (?token=...) e e lido pelo JS da propria pagina, nao pelo Django --
    esta view so serve o shell HTML, igual as demais telas.
    """
    return render(request, 'interface/redefinir_senha.html')


def tela_trocar_senha(request):
    """
    30/07/2026. Qualquer usuario autenticado troca a propria senha
    aqui. O guard de sessao e checado no JS da propria tela (mesmo
    padrao das demais paginas protegidas).
    """
    return render(request, 'interface/trocar_senha.html')


def service_worker(request):
    caminho = Path(__file__).resolve().parent / 'service_worker_src.js'
    return HttpResponse(caminho.read_text(), content_type='application/javascript')
