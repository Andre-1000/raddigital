from django.urls import path

from . import views

app_name = 'interface'

urlpatterns = [
    path('saude/', views.saude, name='saude'),
    path('', views.tela_login, name='raiz'),
    path('entrar/', views.tela_login, name='login'),
    path('inicio/', views.tela_inicio, name='inicio'),
    path('consultar/', views.tela_consulta, name='consulta'),
    path('consultar/<str:numero_rad>/', views.tela_detalhe_rad, name='detalhe_rad'),
    path('meus-rads/', views.tela_meus_rads, name='meus_rads'),
    path('gerenciar-usuarios/', views.tela_gerenciar_usuarios, name='gerenciar_usuarios'),
    path('configuracoes/', views.tela_configuracoes, name='configuracoes'),
    path('dashboard/', views.tela_dashboard, name='dashboard'),
    path('novo-rad/', views.tela_novo_rad, name='novo_rad'),
    path('redefinir-senha/', views.tela_redefinir_senha, name='redefinir_senha'),
    path('trocar-senha/', views.tela_trocar_senha, name='trocar_senha'),
    path('sw.js', views.service_worker, name='service_worker'),
]
