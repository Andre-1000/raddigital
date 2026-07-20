from django.urls import path

from . import views

app_name = 'colaboradores'

urlpatterns = [
    path('buscar/', views.buscar, name='buscar'),
    path('todos/', views.listar_todos, name='listar_todos'),
    path('administrar/', views.listar_para_administrar, name='listar_para_administrar'),
    path('', views.criar, name='criar'),
    path('<int:id_colaborador>/editar/', views.editar, name='editar'),
    path('<int:id_colaborador>/excluir/', views.excluir, name='excluir'),
]
