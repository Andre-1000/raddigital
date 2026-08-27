from django.urls import path

from . import views

app_name = 'usuarios'

urlpatterns = [
    # Autenticacao
    path('login/', views.login, name='login'),
    path('validar-token/', views.validar_token, name='validar_token'),
    path('trocar-senha/', views.trocar_senha, name='trocar_senha'),
    path('meus-dispositivos/', views.listar_meus_dispositivos, name='listar_meus_dispositivos'),
    path('meus-dispositivos/<int:id_token>/encerrar/', views.encerrar_dispositivo, name='encerrar_dispositivo'),
    path('esqueci-senha/', views.solicitar_redefinicao_senha, name='solicitar_redefinicao_senha'),
    path('redefinir-senha/confirmar/', views.confirmar_redefinicao_senha, name='confirmar_redefinicao_senha'),
    # 21/08/2026: Sessoes ativas -- exclusivo do Administrador, aba
    # "Sessoes" dentro de Gerenciar Usuarios. Diferente de
    # meus-dispositivos/ (que so mostra as sessoes do proprio
    # solicitante), estas rotas enxergam e encerram sessoes de
    # QUALQUER usuario do sistema.
    path('sessoes-ativas/', views.listar_sessoes_ativas, name='listar_sessoes_ativas'),
    path('sessoes-ativas/<int:id_token>/encerrar/', views.encerrar_sessao_administrativamente, name='encerrar_sessao_administrativamente'),
    # Gestao de usuarios (EFD secao 4.4)
    path('administrar/', views.listar, name='listar'),
    path('administrar/criar/', views.criar, name='criar'),
    path('administrar/<int:id_usuario>/editar/', views.editar, name='editar'),
    path('administrar/<int:id_usuario>/excluir/', views.excluir, name='excluir'),
    # 25/08/2026: definir senha temporaria -- exclusivo do
    # Administrador, via de emergencia enquanto o envio de e-mail
    # (SMTP) nao estiver funcionando (ver usuarios/views.py para
    # detalhes e justificativa).
    path('administrar/<int:id_usuario>/definir-senha-temporaria/', views.definir_senha_temporaria, name='definir_senha_temporaria'),
    # 25/08/2026: historico de auditoria de quem gerou senha
    # temporaria pra quem (LogSenhaTemporaria) -- exclusivo do
    # Administrador.
    path('administrar/log-senha-temporaria/', views.listar_log_senha_temporaria, name='listar_log_senha_temporaria'),
]
