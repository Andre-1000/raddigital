from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('dados/', views.dados, name='dados'),
    path('exportar-excel/', views.exportar_excel, name='exportar_excel'),
    # 30/09/2026: Sync BD -- exclusivo do Administrador, envia RADs
    # para a planilha do Google (ver rad/google_sheets.py).
    path('sync-bd/', views.sync_bd_dados, name='sync_bd_dados'),
    path('sync-bd/sincronizar/', views.sync_bd_sincronizar, name='sync_bd_sincronizar'),
]
