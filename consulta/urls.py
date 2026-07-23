from django.urls import path

from . import views

app_name = 'consulta'

urlpatterns = [
    path('rads/', views.listar_rads, name='listar_rads'),
    path('meus-rads/', views.listar_meus_rads, name='listar_meus_rads'),
    path('rads/<str:numero_rad>/', views.detalhe_rad, name='detalhe_rad'),
    path('rads/<str:numero_rad>/mensagem/', views.mensagem_copiar, name='mensagem_copiar'),
    path('rads/<str:numero_rad>/pdf/', views.exportar_pdf, name='exportar_pdf'),
    path('rads/<str:numero_rad>/docx/', views.exportar_docx, name='exportar_docx'),
    path('rads/<str:numero_rad>/anexos/<int:id_anexo>/', views.visualizar_anexo, name='visualizar_anexo'),
]
