from django.urls import path

from . import views

app_name = 'rad'

urlpatterns = [
    path('sincronizar/', views.sincronizar, name='sincronizar'),
    path('<str:numero_rad>/cancelar/', views.cancelar_rad, name='cancelar'),
    path('<str:numero_rad>/anexos/<int:id_anexo>/remover/', views.remover_anexo, name='remover_anexo'),
]
