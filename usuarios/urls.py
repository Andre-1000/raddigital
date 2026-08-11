from django.urls import path

from . import views

app_name = 'usuarios'

urlpatterns = [
    # Autenticacao
    path('login/', views.login, name='login'),
    path('validar-token/', views.validar_token, name='validar_token'),
    path('trocar-senha/', views.trocar_senha, name='trocar_senha'),
    path('esqueci-senha/', views.solicitar_redefinicao_senha, name='solicitar_redefinicao_senha'),
    path('redefinir-senha/confirmar/', views.confirmar_redefinicao_senha, name='confirmar_redefinicao_senha'),
    # Gestao de usuarios (EFD secao 4.4)
    path('administrar/', views.listar, name='listar'),
    path('administrar/criar/', views.criar, name='criar'),
    path('administrar/<int:id_usuario>/editar/', views.editar, name='editar'),
    path('administrar/<int:id_usuario>/excluir/', views.excluir, name='excluir'),
]
