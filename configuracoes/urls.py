from django.urls import path

from . import views

app_name = 'configuracoes'

urlpatterns = [
    path('campos/', views.listar_campos, name='listar_campos'),
    path('campos/<str:chave>/desabilitar/', views.desabilitar_campo, name='desabilitar_campo'),
    path('campos/<str:chave>/habilitar/', views.habilitar_campo, name='habilitar_campo'),
    path('campos/<str:chave>/tornar-obrigatorio/', views.tornar_obrigatorio, name='tornar_obrigatorio'),
    path('campos/<str:chave>/tornar-opcional/', views.tornar_opcional, name='tornar_opcional'),
    path('limites-fotos/', views.listar_limites_fotos, name='listar_limites_fotos'),
    path('limites-fotos/<int:id_limite>/atualizar/', views.atualizar_limite_foto, name='atualizar_limite_foto'),
]
