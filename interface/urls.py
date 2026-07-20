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
    path('gerenciar-colaboradores/', views.tela_gerenciar_colaboradores, name='gerenciar_colaboradores'),
    path('novo-rad/', views.tela_novo_rad, name='novo_rad'),
    path('sw.js', views.service_worker, name='service_worker'),
]
