from django.urls import path

from . import views

app_name = 'catalogos'

urlpatterns = [
    path('todos/', views.listar_todos, name='listar_todos'),
]
