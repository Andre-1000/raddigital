from django.urls import path

from . import views

app_name = 'configuracoes'

urlpatterns = [
    path('campos/', views.listar_campos, name='listar_campos'),
    path('campos/<str:chave>/desabilitar/', views.desabilitar_campo, name='desabilitar_campo'),
    path('campos/<str:chave>/habilitar/', views.habilitar_campo, name='habilitar_campo'),
]
